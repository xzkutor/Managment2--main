from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Scheduler run status constants
# ---------------------------------------------------------------------------
class RunStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    # Legacy compat — old "finished" maps to "success"
    FINISHED = "finished"


# ---------------------------------------------------------------------------
# Type aliases for semantic clarity
# ---------------------------------------------------------------------------
# PRICE_NUMERIC: exact decimal storage for monetary/price values.
# Precision=12, scale=4 accommodates most real-world currencies.
# SQLite stores Numeric as TEXT and does exact round-trips; PostgreSQL uses
# NUMERIC natively.  Do NOT use Float for price fields — floating-point
# representation causes rounding errors in comparisons and aggregations.
PRICE_NUMERIC = Numeric(precision=12, scale=4, asdecimal=True)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    categories: Mapped[List["Category"]] = relationship("Category", back_populates="store", cascade="all, delete-orphan")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    scrape_runs: Mapped[List["ScrapeRun"]] = relationship("ScrapeRun", back_populates="store")


# ---------------------------------------------------------------------------
# Scheduler models
# ---------------------------------------------------------------------------

class ScrapeJob(Base):
    """Persistent definition of a schedulable scrape job."""
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    runner_type: Mapped[str] = mapped_column(String(100), nullable=False)
    params_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allow_overlap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_backoff_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    concurrency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    schedules: Mapped[List["ScrapeSchedule"]] = relationship("ScrapeSchedule", back_populates="job", cascade="all, delete-orphan")
    runs: Mapped[List["ScrapeRun"]] = relationship("ScrapeRun", back_populates="job")


class ScrapeSchedule(Base):
    """Schedule configuration for a ScrapeJob."""
    __tablename__ = "scrape_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id"), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "interval" | "cron"
    cron_expr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interval_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    jitter_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    misfire_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="skip")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    job: Mapped[ScrapeJob] = relationship("ScrapeJob", back_populates="schedules")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_categories_store_id_name"),
        Index("ix_categories_normalized_name", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    store: Mapped[Store] = relationship("Store", back_populates="categories")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")


class CategoryMapping(Base):
    __tablename__ = "category_mappings"
    __table_args__ = (
        UniqueConstraint("reference_category_id", "target_category_id", name="uq_category_mappings_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    target_category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    match_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    reference_category: Mapped[Category] = relationship("Category", foreign_keys=[reference_category_id])
    target_category: Mapped[Category] = relationship("Category", foreign_keys=[target_category_id])


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    __table_args__ = (Index("ix_scrape_runs_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stores.id"), nullable=True)
    # Scheduler FK — null for legacy/manual runs
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_jobs.id"), nullable=True)
    run_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    categories_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_changes_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    checkpoint_in_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    checkpoint_out_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Retry metadata — Decision 4 (RFC-008 addendum)
    # retryable: set by runner result; True = scheduler may create a retry run
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # retry_of_run_id: points to the source failed run this was retried from
    retry_of_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    # retry_exhausted: set by scheduler when max_retries is reached for this failure chain
    retry_exhausted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    store: Mapped[Optional[Store]] = relationship("Store", back_populates="scrape_runs")
    job: Mapped[Optional["ScrapeJob"]] = relationship("ScrapeJob", back_populates="runs")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="scrape_run")
    price_history: Mapped[List["ProductPriceHistory"]] = relationship("ProductPriceHistory", back_populates="scrape_run")
    retry_source: Mapped[Optional["ScrapeRun"]] = relationship(
        "ScrapeRun",
        foreign_keys="ScrapeRun.retry_of_run_id",
        remote_side="ScrapeRun.id",
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("store_id", "product_url", name="uq_products_store_id_product_url"),
        Index("ix_products_name_hash", "name_hash"),
        Index("ix_products_normalized_name", "normalized_name"),
        Index("ix_products_scraped_at", "scraped_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    name_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(PRICE_NUMERIC, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    store: Mapped[Store] = relationship("Store", back_populates="products")
    category: Mapped[Optional[Category]] = relationship("Category", back_populates="products")
    scrape_run: Mapped[Optional[ScrapeRun]] = relationship("ScrapeRun", back_populates="products")
    price_history: Mapped[List["ProductPriceHistory"]] = relationship("ProductPriceHistory", back_populates="product", cascade="all, delete-orphan")
    reference_mappings: Mapped[List["ProductMapping"]] = relationship(
        "ProductMapping",
        foreign_keys="ProductMapping.reference_product_id",
        back_populates="reference_product",
    )
    target_mappings: Mapped[List["ProductMapping"]] = relationship(
        "ProductMapping",
        foreign_keys="ProductMapping.target_product_id",
        back_populates="target_product",
    )


class ProductMapping(Base):
    __tablename__ = "product_mappings"
    __table_args__ = (
        UniqueConstraint("reference_product_id", "target_product_id", name="uq_product_mappings_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    target_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    match_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    reference_product: Mapped[Product] = relationship("Product", foreign_keys=[reference_product_id], back_populates="reference_mappings")
    target_product: Mapped[Product] = relationship("Product", foreign_keys=[target_product_id], back_populates="target_mappings")


class GapItemStatus(Base):
    """Persisted review status for target-only products in an assortment gap review.

    Only non-default states are stored:
    - ``in_progress`` – content manager is working on this item
    - ``done``        – content manager has finished reviewing this item

    The implicit default state ``new`` is represented by the *absence* of a row.
    """
    __tablename__ = "gap_item_statuses"
    __table_args__ = (
        UniqueConstraint(
            "reference_category_id",
            "target_product_id",
            name="uq_gap_item_statuses_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    target_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    reference_category: Mapped["Category"] = relationship("Category", foreign_keys=[reference_category_id])
    target_product: Mapped["Product"] = relationship("Product", foreign_keys=[target_product_id])


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (Index("ix_price_history_product_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    # price: exact numeric — see PRICE_NUMERIC note above
    price: Mapped[Optional[Decimal]] = mapped_column(PRICE_NUMERIC, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="price_history")
    scrape_run: Mapped[Optional[ScrapeRun]] = relationship("ScrapeRun", back_populates="price_history")

