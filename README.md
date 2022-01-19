# Python Solana NFT snapshot tools

A suite of handy tools (in python script form) to get information about an NFT collection on Solana including the token list from a CandyMachine ID,
holder snapshots as CSV, holder wallet distribution, and trait rarity.

It runs (relatively) quickly due to asyncio usage, and caches downloaded data for performance reasons.

# Usage
    % python nft_snapshot.py -h
    Usage: nft_snapshot.py [options]

    Options:
      -h, --help            show this help message and exit
      -t                    Get the token list for the given CM ID (requires
                            passing --cmid)
      -o                    Get and print the overall holder counts
      -a                    Get and print the overall metadata attribute
                            distribution
      -s                    Get and output the snapshot file to the outfile name
                            from -f
      -f FILE, --file=FILE  Write snapshot to FILE (defaults to snapshot.csv)
      --cmid=CANDYMACHINE_ID
                            Use CANDYMACHINE_ID to fetch tokens
      --cmv2                Use Candy Machine v2 method to fetch tokens from CM ID
      --bust-cache          Clear out any existing cache data for this token file

# Examples
    % python nft_snapshot.py -toas --cmid=4wTTi885HkQ6awqRGQkHAdXXzE46DyqLNXtfo1uz5ub3 tokenlist_mf.txt
Fetch token information for the Mindfolk collection into `tokenlist_mf.txt` then print a holder count list, print a trait rarity analysis,
and output a CSV snapshot of token information to `snapshot.csv` (the default location). Use cached data, if present.

    % python nft_snapshot.py -s -f trash_snap.csv --bust-cache tokenlist_trash.txt
Using an existing token list from tokenlist_trash.txt, output a fresh CSV snapshot (not relying on cached data)
to `trash_snap.csv`.

# Example CM IDs
* Aurory (10k tokens): `9vwYtcJsH1MskNaixcjgNBnvBDkTBhyg25umod1rgMQL`
* Pit's Trash Bin (2k tokens, no trait metadata): `CApZmLZAwjTm59pc6rKJ85sux4wCJsLS7RMV1pUkMeVK`
* Monkey Kingdom (2222 tokens): `C3UphYJYqTab4Yrr64V8wSAxeM7Wr9NUauyYGn7aomTJ`
* Mindfolk (778 tokens): `4wTTi885HkQ6awqRGQkHAdXXzE46DyqLNXtfo1uz5ub3`

# TODO
- Unit tests
- Classes?
- Add statistical rarity analysis and ranking of a particular ID, and add to snapshot
