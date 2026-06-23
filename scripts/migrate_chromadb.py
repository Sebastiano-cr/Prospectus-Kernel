#!/usr/bin/env python3
"""
Migrate ChromaDB collections from kirin_* prefix to prospectus_kernel_* prefix.
Creates new collections, copies all data, verifies counts, and optionally drops old ones.

Usage:
    python scripts/migrate_chromadb.py [--path ./data/chroma] [--drop-old]
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.store import ChromaStore

OLD_PREFIX = "kirin_"
NEW_PREFIX = "prospectus_kernel_"


async def migrate(path: str, drop_old: bool = False) -> None:
    store = ChromaStore(path=path, collection_prefix=OLD_PREFIX)
    await store.initialize()

    client = store._client
    if not client:
        print("Failed to initialize ChromaDB client")
        return

    collections = client.list_collections()
    old_collections = [c for c in collections if c.name.startswith(OLD_PREFIX)]

    if not old_collections:
        print(f"No collections with prefix '{OLD_PREFIX}' found at {path}")
        await store.shutdown()
        return

    print(f"Found {len(old_collections)} collection(s) to migrate:")
    for c in old_collections:
        count = c.count()
        print(f"  - {c.name} ({count} records)")

    for old_coll in old_collections:
        old_name = old_coll.name
        new_name = NEW_PREFIX + old_name[len(OLD_PREFIX):]
        count = old_coll.count()

        if count == 0:
            print(f"  Skipping {old_name} (empty)")
            continue

        new_coll = client.get_or_create_collection(
            name=new_name,
            metadata=old_coll.metadata,
        )

        BATCH = 100
        offset = 0
        total_copied = 0

        while offset < count:
            results = old_coll.get(offset=offset, limit=BATCH)
            if not results["ids"]:
                break
            new_coll.upsert(
                ids=results["ids"],
                embeddings=results.get("embeddings"),
                documents=results.get("documents"),
                metadatas=results.get("metadatas"),
            )
            total_copied += len(results["ids"])
            offset += BATCH
            print(f"  {old_name} → {new_name}: {total_copied}/{count}")

        new_count = new_coll.count()
        if new_count == count:
            print(f"  ✓ {old_name} → {new_name}: {count} records migrated successfully")
        else:
            print(f"  ✗ MISMATCH: {old_name} had {count}, {new_name} has {new_count}")

    await store.shutdown()

    if drop_old:
        print("\nDropping old collections...")
        store2 = ChromaStore(path=path, collection_prefix=OLD_PREFIX)
        await store2.initialize()
        client2 = store2._client
        if client2:
            for old_coll in old_collections:
                client2.delete_collection(old_coll.name)
                print(f"  Deleted {old_coll.name}")
        await store2.shutdown()

    print("\nMigration complete!")


def main():
    parser = argparse.ArgumentParser(description="Migrate ChromaDB collections from kirin_ to prospectus_kernel_ prefix")
    parser.add_argument("--path", default="./data/chroma", help="Path to ChromaDB data directory")
    parser.add_argument("--drop-old", action="store_true", help="Drop old collections after migration")
    args = parser.parse_args()

    asyncio.run(migrate(path=args.path, drop_old=args.drop_old))


if __name__ == "__main__":
    main()
