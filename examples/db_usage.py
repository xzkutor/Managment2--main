from __future__ import annotations

from datetime import timezone, datetime

from pricewatch.db import init_engine, init_db, get_session_factory
from pricewatch.db.config import session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import upsert_category, create_category_mapping
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import create_product_mapping
from pricewatch.db.repositories.scrape_run_repository import start_run, finish_run


def main():
    engine = init_engine({})
    init_db(engine)
    session_factory = get_session_factory(engine)

    with session_scope(session_factory) as session:
        reference_store = get_or_create_store(session, "reference-shop", is_reference=True, base_url="https://ref.example")
        target_store = get_or_create_store(session, "other-shop", is_reference=False, base_url="https://other.example")

    with session_scope(session_factory) as session:
        run = start_run(session, store_id=target_store.id, run_type="demo")

        ref_cat = upsert_category(session, store_id=reference_store.id, name="Hockey Skates", url="https://ref.example/c/skates")
        tgt_cat = upsert_category(session, store_id=target_store.id, name="Hockey Skates", url="https://other.example/c/skates")
        create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="exact", confidence=0.95)

        product = upsert_product(
            session,
            store_id=target_store.id,
            product_url="https://other.example/p/123",
            name="Bauer Vapor X3",
            price=199.99,
            currency="USD",
            category_id=tgt_cat.id,
            source_url="https://other.example/p/123",
            scrape_run_id=run.id,
        )
        ref_product = upsert_product(
            session,
            store_id=reference_store.id,
            product_url="https://ref.example/p/123",
            name="Bauer Vapor X3",
            price=209.99,
            currency="USD",
            category_id=ref_cat.id,
            source_url="https://ref.example/p/123",
            scrape_run_id=run.id,
        )
        create_product_mapping(
            session,
            reference_product_id=ref_product.id,
            target_product_id=product.id,
            match_status="auto",
            confidence=0.9,
        )
        finish_run(session, run.id)

    print("Demo data inserted. Run alembic upgrade head to migrate schema in production.")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import timezone, datetime

from pricewatch.db import init_engine, init_db, get_session_factory
from pricewatch.db.config import session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import upsert_category, create_category_mapping
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import create_product_mapping
from pricewatch.db.repositories.scrape_run_repository import start_run, finish_run


def main():
    engine = init_engine({})
    init_db(engine)
    session_factory = get_session_factory(engine)

    with session_scope(session_factory) as session:
        reference_store = get_or_create_store(session, "reference-shop", is_reference=True, base_url="https://ref.example")
        target_store = get_or_create_store(session, "other-shop", is_reference=False, base_url="https://other.example")

    with session_scope(session_factory) as session:
        run = start_run(session, store_id=target_store.id, run_type="demo")

        ref_cat = upsert_category(session, store_id=reference_store.id, name="Hockey Skates", url="https://ref.example/c/skates")
        tgt_cat = upsert_category(session, store_id=target_store.id, name="Hockey Skates", url="https://other.example/c/skates")
        create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="exact", confidence=0.95)

        product = upsert_product(
            session,
            store_id=target_store.id,
            product_url="https://other.example/p/123",
            name="Bauer Vapor X3",
            price=199.99,
            currency="USD",
            category_id=tgt_cat.id,
            source_url="https://other.example/p/123",
            scrape_run_id=run.id,
        )
        ref_product = upsert_product(
            session,
            store_id=reference_store.id,
            product_url="https://ref.example/p/123",
            name="Bauer Vapor X3",
            price=209.99,
            currency="USD",
            category_id=ref_cat.id,
            source_url="https://ref.example/p/123",
            scrape_run_id=run.id,
        )
        create_product_mapping(
            session,
            reference_product_id=ref_product.id,
            target_product_id=product.id,
            match_status="auto",
            confidence=0.9,
        )
        finish_run(session, run.id)

    print("Demo data inserted. Run alembic upgrade head to migrate schema in production.")


if __name__ == "__main__":
    main()

