# Fix Cloudflare Zero-Trust Tunnel DNS Records

Adding or removing hostnames to your Zero-Trust Tunnel configuration automatically creates appropriate DNS CNAME records in the appropriate zone.
Unfortunately, this process sometimes fails.
For example, you may run into this issue: https://github.com/cloudflare/cloudflared/issues/354.

This script fixes your DNS entries as follows:

* Update DNS records for hostnames present in the DNS zone, but not pointing to the correct tunnel.
* Add DNS records for hostnames defined in tunnels but not your DNS zone.
* Remove DNS records pointing to a non-existing tunnel or a tunnel that does not define the record's hostname.


## Usage

Install Python. Create a virtual environment and activate it.

    python -m venv .venv
    source .venv/bin/activate

Install the required dependencies. There are pinned dependencies in `requirements.txt`, and unpinned ones in `requirements.in`. (The only dependency is the Cloudflare API client, really.)

    pip install -r requirements.txt

Define environment variables that allow you to authenticate with the CloudFlare API, and a variable `FIX_CF_ACCOUNT_ID` specifying your account ID.

    export CLOUDFLARE_API_KEY=your-api-key
    export CLOUDFLARE_EMAIL=your-email-address
    export FIX_CF_ACCOUNT_ID=your-account-id

Run the script.

    ./fix.py


## How it works

The script uses the CloudFlare API to retrieve the list of tunnels and the list of all DNS records of all zones in your account.
It then compares the two lists and updates the DNS records accordingly.
For DNS record removal, it only considers DNS records pointing to Cloudflare tunnels.

The script tells you what it is going to do, and prompts for confirmation before making any changes.


## Limitations

The script will want to remove any CNAME records to tunnels you do not own.

The script assumes that the DNS zones for which you create tunnels are managed by CloudFlare and reside in the same account as the tunnels.

I created this script for personal use; it may not work for you. No guarantees.
