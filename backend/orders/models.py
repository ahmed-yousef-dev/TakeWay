"""
Commerce domain models for TakeWay.

Includes:
- DeliveryAddress
- Cart & CartItem
- Order, SubOrder & OrderItem (with immutable snapshots)
- AnythingRequest & AnythingRequestImage
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

from common.models import SoftDeleteMixin, TimestampMixin


class DeliveryAddress(SoftDeleteMixin, TimestampMixin):
    """
    A saved delivery destination for a customer.
    Checkout requires one of these to ensure a valid delivery point.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="delivery_addresses",
        verbose_name=_("user"),
    )
    label = models.CharField(
        _("label"),
        max_length=50,
    )
    address_details = models.TextField(
        _("address details"),
        help_text=_("Full description of the delivery address/landmark."),
    )
    # Storing as simple strings or decimals for Phase 1. 
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("delivery address")
        verbose_name_plural = _("delivery addresses")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.label} - {self.user.name}"

    def anonymize(self):
        """
        Anonymizes the address details for soft deletion.
        """
        self.address_details = "Deleted Address"
        self.latitude = None
        self.longitude = None
        self.save(update_fields=["address_details", "latitude", "longitude"])


class Cart(TimestampMixin):
    """
    A customer's shopping cart.
    Can contain items from multiple businesses.
    """

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="cart",
        verbose_name=_("user"),
    )

    class Meta:
        verbose_name = _("cart")
        verbose_name_plural = _("carts")

    def __str__(self):
        return f"Cart for {self.user.name}"


class CartItem(TimestampMixin):
    """
    An individual item in the cart.
    Belongs to a specific Business via the Product.
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("cart"),
    )
    product = models.ForeignKey(
        "businesses.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name=_("product"),
    )
    variant = models.ForeignKey(
        "businesses.ProductVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_items",
        verbose_name=_("product variant"),
    )
    quantity = models.PositiveIntegerField(
        _("quantity"),
        default=1,
        validators=[MinValueValidator(1)],
    )
    note = models.TextField(
        _("note"),
        blank=True,
        help_text=_("Optional customer note for this item."),
    )

    class Meta:
        verbose_name = _("cart item")
        verbose_name_plural = _("cart items")
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product", "variant"],
                name="unique_cart_item",
            )
        ]

    def __str__(self):
        variant_str = f" ({self.variant.name})" if self.variant else ""
        return f"{self.quantity} x {self.product.name}{variant_str}"


class Order(SoftDeleteMixin, TimestampMixin):
    """
    The parent order representing the customer's entire checkout.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")          # Needs admin review
        ACCEPTED = "accepted", _("Accepted")       # Admin accepted, being processed
        ON_WAY = "on_way", _("On the Way")         # Out for delivery
        DELIVERED = "delivered", _("Delivered")    # Delivered to customer
        CANCELLED = "cancelled", _("Cancelled")    # Cancelled by customer or admin

    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("customer"),
    )
    delivery_address = models.ForeignKey(
        DeliveryAddress,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("delivery address"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    confirmed_eta = models.CharField(
        _("confirmed ETA"),
        max_length=50,
        blank=True,
        default="",
        help_text=_("e.g. '45 mins'. Set by admin when accepting the order."),
    )
    # Totals are snapshotted here to prevent drift
    subtotal = models.DecimalField(
        _("subtotal"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Sum of all order items (EGP)."),
    )
    delivery_fee = models.DecimalField(
        _("delivery fee"),
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text=_("Delivery fee charged for this order (EGP)."),
    )
    total_amount = models.DecimalField(
        _("total amount"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Total amount to be paid by customer (EGP)."),
    )

    class Meta:
        verbose_name = _("order")
        verbose_name_plural = _("orders")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.customer.name}"


class SubOrder(TimestampMixin):
    """
    A grouping of items within an Order that come from a single Business.
    Keeps fulfillment internal and traceable.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="sub_orders",
        verbose_name=_("order"),
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.PROTECT,
        related_name="sub_orders",
        verbose_name=_("business"),
    )
    subtotal = models.DecimalField(
        _("subtotal"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Sum of all items in this sub-order (EGP)."),
    )

    class Meta:
        verbose_name = _("sub-order")
        verbose_name_plural = _("sub-orders")
        ordering = ["created_at"]

    def __str__(self):
        return f"SubOrder #{self.id} for {self.business.name} (Order #{self.order.id})"


class OrderItem(TimestampMixin):
    """
    An immutable snapshot of a purchased item.
    """

    sub_order = models.ForeignKey(
        SubOrder,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("sub-order"),
    )
    # References to actual products/variants for convenience, but prices/names are copied.
    product = models.ForeignKey(
        "businesses.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name=_("product"),
    )
    variant = models.ForeignKey(
        "businesses.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name=_("product variant"),
    )
    
    # Immutable fields copied at checkout
    product_name = models.CharField(_("product name"), max_length=200)
    variant_name = models.CharField(_("variant name"), max_length=100, blank=True)
    unit_price = models.DecimalField(_("unit price"), max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
    total_price = models.DecimalField(_("total price"), max_digits=10, decimal_places=2)
    
    note = models.TextField(_("note"), blank=True)

    class Meta:
        verbose_name = _("order item")
        verbose_name_plural = _("order items")
        ordering = ["created_at"]

    def __str__(self):
        name = self.product_name
        if self.variant_name:
            name += f" ({self.variant_name})"
        return f"{self.quantity} x {name}"

    @classmethod
    def create_snapshot(cls, cart_item, sub_order):
        """
        Creates an immutable OrderItem snapshot from a CartItem.
        Locks in the current price (including active offers) and names so future catalog edits don't affect this order.
        """
        offer = cart_item.product.get_best_active_offer()
        
        if cart_item.variant:
            base_price = cart_item.variant.selling_price
            variant_name = cart_item.variant.name
        else:
            base_price = cart_item.product.selling_price
            variant_name = ""

        if offer:
            unit_price = offer.calculate_discounted_price(base_price)
        else:
            unit_price = base_price

        total_price = unit_price * cart_item.quantity

        return cls(
            sub_order=sub_order,
            product=cart_item.product,
            variant=cart_item.variant,
            product_name=cart_item.product.name,
            variant_name=variant_name,
            unit_price=unit_price,
            quantity=cart_item.quantity,
            total_price=total_price,
            note=cart_item.note
        )


class AnythingRequest(SoftDeleteMixin, TimestampMixin):
    """
    A custom request from a user for anything not in the catalog.
    Operationally separate from the main cart-to-order flow for Phase 1.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        QUOTED = "quoted", _("Quoted")
        ACCEPTED = "accepted", _("Accepted")
        REJECTED = "rejected", _("Rejected")
        ORDERED = "ordered", _("Converted to Order")

    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="anything_requests",
        verbose_name=_("customer"),
    )
    delivery_address = models.ForeignKey(
        DeliveryAddress,
        on_delete=models.PROTECT,
        related_name="anything_requests",
        verbose_name=_("delivery address"),
    )
    request_text = models.TextField(
        _("request text"),
        blank=True,
        help_text=_("What does the customer want?"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_note = models.TextField(
        _("admin note"),
        blank=True,
        help_text=_("Internal notes for the operations team."),
    )

    class Meta:
        verbose_name = _("anything request")
        verbose_name_plural = _("anything requests")
        ordering = ["-created_at"]

    def __str__(self):
        return f"AnythingRequest #{self.id} - {self.customer.name}"


class AnythingRequestImage(TimestampMixin):
    """
    Optional images attached to an AnythingRequest.
    """

    anything_request = models.ForeignKey(
        AnythingRequest,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("anything request"),
    )
    image = models.ImageField(
        _("image"),
        upload_to="anything_requests/images/",
    )

    class Meta:
        verbose_name = _("anything request image")
        verbose_name_plural = _("anything request images")
        ordering = ["created_at"]

    def __str__(self):
        return f"Image for AnythingRequest #{self.anything_request_id}"
