#!/usr/bin/env python
from dataclasses import dataclass, asdict
from functools import cache
import CloudFlare
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
ACCOUNT_ID = os.environ["FIX_CF_ACCOUNT_ID"]


@dataclass(frozen=True)
class Record:
    id: str | None
    zone_id: str
    type: str
    content: str
    proxiable: bool
    proxied: bool
    ttl: int

    def data(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in ["id", "zone_id"]}


@cache
def tunnels():
    return cf.accounts.cfd_tunnel.get(ACCOUNT_ID, params={"is_deleted": "false"})


@cache
def zones():
    return cf.zones.get()


@cache
def zone_name_to_id(zone_name: str) -> str:
    for zone in zones():
        if zone["name"] == zone_name:
            return zone["id"]
    raise ValueError(f"zone {zone_name} not found")


def desired() -> dict["Record"]:
    desired = {}
    for tunnel in tunnels():
        logger.info(
            "Retrieving desired records for tunnel %s (i: %s)",
            tunnel["name"],
            tunnel["id"],
        )
        config = cf.accounts.cfd_tunnel.configurations(ACCOUNT_ID, tunnel["id"])
        for elem in config["config"]["ingress"]:
            if "hostname" not in elem:
                continue
            zone_name = ".".join(elem["hostname"].split(".")[1:])
            zone_id = zone_name_to_id(zone_name)
            desired[elem["hostname"]] = Record(
                id=None,
                zone_id=zone_id,
                type="CNAME",
                content=tunnel["id"] + ".cfargotunnel.com",
                proxiable=True,
                proxied=True,
                ttl=1,
            )
    return desired


def current() -> dict["Record"]:
    records = {}
    for zone in zones():
        logger.info(
            "Retrieving current records for zone %s (i: %s)",
            zone["name"],
            zone["id"],
        )
        zone_id = zone["id"]
        zone_records = cf.zones.dns_records.get(zone_id)
        for record in zone_records:
            logger.debug("record in current state: %s", record)
            records[record["name"]] = Record(
                id=record["id"],
                zone_id=record["zone_id"],
                type=record["type"],
                content=record["content"],
                proxiable=record["proxiable"],
                proxied=record["proxied"],
                ttl=record["ttl"],
            )
    return records


def process(prompt: bool = True):
    _desired = desired()
    _current = current()
    create(_desired, _current, prompt)
    update(_desired, _current, prompt)
    delete(_desired, _current, prompt)


def create(desired: dict["Record"], current: dict["Record"], prompt: bool = True):
    """Creates the records that exist in the desired state but not in current state."""
    records = {k: desired[k] for k in desired.keys() - current.keys()}
    if len(records) == 0:
        logger.info("no records to create")
        return
    print("Planning to create entries for the following domains: ")
    for k in records.keys():
        print("\t-" + k)
    if prompt and input("Proceed? [y/N] ") != "y":
        logger.info("not creating records")
        return
    for entry, props in records.items():
        logger.info("creating record for %s in zone %s", entry, props.zone_id)
        cf.zones.dns_records.post(
            props.zone_id,
            data={"name": entry, **props.data()},
        )


def delete(desired: dict["Record"], current: dict["Record"], prompt: bool = True):
    """Deletes tunnel-related records existing in current state but not in desired state."""
    records = {
        k: current[k]
        for k in current.keys() - desired.keys()
        if k.endswith(".cfargotunnel.com")
    }
    if len(records) == 0:
        logger.info("no records to delete")
        return
    print("Some records point to inactive tunnels or tunnels not owned by you.")
    print("Planning to delete records for the following domains: ")
    for k in records.keys():
        print("\t-" + k)
    if prompt and input("Proceed? [y/N] ") != "y":
        logger.info("not deleting records")
    for entry, props in records.items():
        logger.info("deleting record for %s in zone %s", entry, props.zone_id)
        cf.zones.dns_records.delete(props.zone_id, props.id)


def update(desired: dict["Record"], current: dict["Record"], prompt: bool = True):
    """Updates records that exist both in the current and the desired state with the desired contents."""

    def truedesire(desired_record: Record, current_record) -> Record:
        """Returns a record with the contents of the desired record, but the id of the current one."""
        return Record(**{**asdict(desired_record), "id": current_record.id})

    records = {
        k: truedesire(desired[k], current[k])
        for k in desired.keys() & current.keys()
        if truedesire(desired[k], current[k]) != current[k]
    }
    if len(records) == 0:
        logger.info("no records to update")
        return
    print("Planning to update entries for the following domains: ")
    for k in records.keys():
        print("\t-" + k)
    if prompt and input("Proceed? [y/N] ") != "y":
        logger.info("not updating records")
        return
    for entry, props in records.items():
        logger.info(
            "updating record for %s in zone %s (id %s)", entry, props.zone_id, props.id
        )
        cf.zones.dns_records.patch(
            props.zone_id,
            props.id,
            data={"name": entry, **props.data()},
        )


if __name__ == "__main__":
    cf = CloudFlare.CloudFlare(debug=False)
    process()
