from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    run_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    categories_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_changes_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    store: Mapped[Optional[Store]] = relationship("Store", back_populates="scrape_runs")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="scrape_run")
    price_history: Mapped[List["ProductPriceHistory"]] = relationship("ProductPriceHistory", back_populates="scrape_run")


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
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (Index("ix_price_history_product_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="price_history")
    scrape_run: Mapped[Optional[ScrapeRun]] = relationship("ScrapeRun", back_populates="price_history")

