"""
Management command to seed Phase 1A demo data for TakeWay.

Target locations:
- Banha (City, Qalyubia)
- Aghour (Village, Qalyubia)
- Quesna (City, Menofia)
- Arab El-Raml (Village, Menofia)

Usage:
  python manage.py seed_data                     # Seed data if no data exists
  python manage.py seed_data --clear             # Clear ONLY existing data (no seeding)
  python manage.py seed_data --reset             # Clear existing data AND THEN seed new data
"""

import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from locations.models import Governorate, Location
from businesses.models import (
    BusinessCategory,
    Business,
    WorkingHour,
    ProductCategory,
    Product,
    ProductVariant,
)
from promotions.models import Banner, Offer


class Command(BaseCommand):
    help = "Seeds demo data for Phase 1A (Locations, Accounts, Businesses, Products, Variants, Working Hours)"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--clear",
            action="store_true",
            help="ONLY clear existing Phase 1A dummy data (no seeding)",
        )
        group.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing Phase 1A dummy data, AND THEN seed new data",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        clear = options.get("clear", False)
        reset = options.get("reset", False)

        if clear or reset:
            self.stdout.write(self.style.WARNING("Clearing existing Phase 1 data..."))
            Banner.objects.all().delete()
            Offer.objects.all().delete()
            ProductVariant.objects.all().delete()
            Product.objects.all().delete()
            ProductCategory.objects.all().delete()
            WorkingHour.objects.all().delete()
            Business.objects.all().delete()
            BusinessCategory.objects.all().delete()
            # Delete non-superuser users
            User.objects.filter(is_superuser=False).delete()
            Location.objects.all().delete()
            Governorate.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Existing data cleared successfully!"))
            
            if clear:
                return

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Phase 1A Demo Data..."))

        # ----------------------------------------------------------------------
        # 1. Governorates & Locations
        # ----------------------------------------------------------------------
        qalyubia, _ = Governorate.objects.get_or_create(name="القليوبية")
        menofia, _ = Governorate.objects.get_or_create(name="المنوفية")

        banha, _ = Location.objects.get_or_create(
            name="بنها",
            governorate=qalyubia,
            defaults={
                "type": Location.LocationType.CITY,
                "delivery_fee": Decimal("15.00"),
                "minimum_order_amount": Decimal("50.00"),
            },
        )

        aghour, _ = Location.objects.get_or_create(
            name="أجهور",
            governorate=qalyubia,
            defaults={
                "type": Location.LocationType.VILLAGE,
                "delivery_fee": Decimal("10.00"),
                "minimum_order_amount": Decimal("30.00"),
            },
        )

        quesna, _ = Location.objects.get_or_create(
            name="قويسنا",
            governorate=menofia,
            defaults={
                "type": Location.LocationType.CITY,
                "delivery_fee": Decimal("15.00"),
                "minimum_order_amount": Decimal("50.00"),
            },
        )

        arab_el_raml, _ = Location.objects.get_or_create(
            name="عرب الرمل",
            governorate=menofia,
            defaults={
                "type": Location.LocationType.VILLAGE,
                "delivery_fee": Decimal("10.00"),
                "minimum_order_amount": Decimal("25.00"),
            },
        )

        self.stdout.write(self.style.SUCCESS("[OK] Governorates & Locations created (Banha, Aghour, Quesna, Arab El-Raml)"))

        # ----------------------------------------------------------------------
        # 2. Business Categories
        # ----------------------------------------------------------------------
        cat_restaurants, _ = BusinessCategory.objects.get_or_create(
            name="مطاعم", defaults={"sort_order": 1}
        )
        cat_supermarkets, _ = BusinessCategory.objects.get_or_create(
            name="سوبر ماركت", defaults={"sort_order": 2}
        )
        cat_pharmacies, _ = BusinessCategory.objects.get_or_create(
            name="صيدليات", defaults={"sort_order": 3}
        )
        cat_bakeries, _ = BusinessCategory.objects.get_or_create(
            name="مخابز وحلويات", defaults={"sort_order": 4}
        )

        self.stdout.write(self.style.SUCCESS("[OK] Business Categories created"))

        # ----------------------------------------------------------------------
        # 3. User Accounts (Superadmin, Customers, Owners)
        # ----------------------------------------------------------------------
        # Admin Superuser
        admin_user, admin_created = User.objects.get_or_create(
            phone="01001234567",
            defaults={
                "name": "مدير النظام (Admin)",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin_created:
            admin_user.set_password("AdminPassword123!")
            admin_user.save()

        # Customer 1 (Banha)
        customer_banha, customer_banha_created = User.objects.get_or_create(
            phone="01099991111",
            defaults={
                "name": "أحمد علي (مستخدم بنها)",
                "role": User.Role.CUSTOMER,
                "location": banha,
            },
        )
        if customer_banha_created:
            customer_banha.set_password("password123")
            customer_banha.save()

        # Customer 2 (Arab El-Raml)
        customer_raml, customer_raml_created = User.objects.get_or_create(
            phone="01088882222",
            defaults={
                "name": "محمود حسن (مستخدم عرب الرمل)",
                "role": User.Role.CUSTOMER,
                "location": arab_el_raml,
            },
        )
        if customer_raml_created:
            customer_raml.set_password("password123")
            customer_raml.save()

        # Owners
        owner_koshary, owner_koshary_created = User.objects.get_or_create(
            phone="01011113333",
            defaults={"name": "الأسطى سعيد", "role": User.Role.BUSINESS_OWNER, "location": banha},
        )
        if owner_koshary_created:
            owner_koshary.set_password("password123")
            owner_koshary.save()

        owner_basha, owner_basha_created = User.objects.get_or_create(
            phone="01022224444",
            defaults={"name": "الحاج إبراهيم", "role": User.Role.BUSINESS_OWNER, "location": banha},
        )
        if owner_basha_created:
            owner_basha.set_password("password123")
            owner_basha.save()

        owner_ezaby, owner_ezaby_created = User.objects.get_or_create(
            phone="01033335555",
            defaults={"name": "د. طارق مصطفى", "role": User.Role.BUSINESS_OWNER, "location": banha},
        )
        if owner_ezaby_created:
            owner_ezaby.set_password("password123")
            owner_ezaby.save()

        owner_pizza, owner_pizza_created = User.objects.get_or_create(
            phone="01044446666",
            defaults={"name": "الشيف هاني", "role": User.Role.BUSINESS_OWNER, "location": quesna},
        )
        if owner_pizza_created:
            owner_pizza.set_password("password123")
            owner_pizza.save()

        owner_baraka, owner_baraka_created = User.objects.get_or_create(
            phone="01055557777",
            defaults={"name": "المعلم رجب", "role": User.Role.BUSINESS_OWNER, "location": arab_el_raml},
        )
        if owner_baraka_created:
            owner_baraka.set_password("password123")
            owner_baraka.save()

        owner_raml_bakery, owner_raml_bakery_created = User.objects.get_or_create(
            phone="01066668888",
            defaults={"name": "أبو حامد", "role": User.Role.BUSINESS_OWNER, "location": arab_el_raml},
        )
        if owner_raml_bakery_created:
            owner_raml_bakery.set_password("password123")
            owner_raml_bakery.save()

        self.stdout.write(self.style.SUCCESS("[OK] Test Accounts created (Admin, Customers, Owners)"))

        # Helper to seed 7 working hours for a business
        def create_working_hours(business, open_time=datetime.time(8, 0), close_time=datetime.time(23, 0), is_24h=False):
            for day in range(7):
                WorkingHour.objects.get_or_create(
                    business=business,
                    day_of_week=day,
                    defaults={
                        "opening_time": datetime.time(0, 0) if is_24h else open_time,
                        "closing_time": datetime.time(23, 59) if is_24h else close_time,
                        "is_closed": False,
                    },
                )

        # ----------------------------------------------------------------------
        # 4. Businesses, Product Categories, Products & Variants
        # ----------------------------------------------------------------------

        # Business 1: كشري التحرير - بنها
        biz_koshary, _ = Business.objects.get_or_create(
            name="كشري التحرير",
            location=banha,
            defaults={
                "description": "أشهر أطباق الكشري المصري والطواجن بنكهة مميزة",
                "category": cat_restaurants,
                "owner": owner_koshary,
                "phone": "01011113333",
                "address": "شارع أTraditional - بنها",
                "avg_rating": Decimal("4.70"),
                "review_count": 128,
                "is_featured": True,
            },
        )
        create_working_hours(biz_koshary, datetime.time(10, 0), datetime.time(23, 0))

        pc_koshary_main, _ = ProductCategory.objects.get_or_create(name="أطباق كشري", business=biz_koshary, defaults={"sort_order": 1})
        pc_koshary_sides, _ = ProductCategory.objects.get_or_create(name="إضافات ومشروبات", business=biz_koshary, defaults={"sort_order": 2})

        p_koshary_super, _ = Product.objects.get_or_create(
            name="كشري سوبر",
            business=biz_koshary,
            defaults={
                "description": "كشري مصري أصيل مع صلصة وحمص ودقة",
                "product_category": pc_koshary_main,
                "cost_price": Decimal("25.00"),
                "selling_price": Decimal("30.00"),
                "is_available": True,
            },
        )

        p_koshary_family, _ = Product.objects.get_or_create(
            name="كشري عائلي (أحجام)",
            business=biz_koshary,
            defaults={
                "description": "طبق كشري مشكل متوفر بأحجام مختلفة للمجموعات",
                "product_category": pc_koshary_main,
                "cost_price": Decimal("40.00"),
                "selling_price": Decimal("50.00"),
                "is_available": True,
            },
        )
        # Variants for family koshary
        ProductVariant.objects.get_or_create(product=p_koshary_family, name="حجم وسط", defaults={"cost_price": Decimal("35.00"), "selling_price": Decimal("45.00")})
        ProductVariant.objects.get_or_create(product=p_koshary_family, name="حجم كبير", defaults={"cost_price": Decimal("50.00"), "selling_price": Decimal("65.00")})
        ProductVariant.objects.get_or_create(product=p_koshary_family, name="حجم جامبو", defaults={"cost_price": Decimal("70.00"), "selling_price": Decimal("90.00")})

        Product.objects.get_or_create(
            name="طاجن مكرونة باللحمة المفرومة",
            business=biz_koshary,
            defaults={
                "description": "طاجن مكرونة بالفرن باللحمة البلدي",
                "product_category": pc_koshary_main,
                "cost_price": Decimal("30.00"),
                "selling_price": Decimal("40.00"),
            },
        )
        Product.objects.get_or_create(
            name="زجاجة كوكاكولا 1 لتر",
            business=biz_koshary,
            defaults={
                "product_category": pc_koshary_sides,
                "cost_price": Decimal("15.00"),
                "selling_price": Decimal("20.00"),
            },
        )

        # Business 2: سوبر ماركت الباشا - بنها
        biz_basha, _ = Business.objects.get_or_create(
            name="سوبر ماركت الباشا",
            location=banha,
            defaults={
                "description": "جميع المواد الغذائية والمنتجات المنزلية بأسعار جملة",
                "category": cat_supermarkets,
                "owner": owner_basha,
                "phone": "01022224444",
                "address": "بجوار موقف بنها الجديد",
                "avg_rating": Decimal("4.50"),
                "review_count": 85,
                "is_featured": False,
            },
        )
        create_working_hours(biz_basha, datetime.time(8, 0), datetime.time(0, 0))

        pc_basha_dairy, _ = ProductCategory.objects.get_or_create(name="منتجات ألبان", business=biz_basha, defaults={"sort_order": 1})
        pc_basha_groceries, _ = ProductCategory.objects.get_or_create(name="بقالة ومعلبات", business=biz_basha, defaults={"sort_order": 2})

        Product.objects.get_or_create(
            name="حليب جهينة كامل الدسم 1 لتر",
            business=biz_basha,
            defaults={
                "product_category": pc_basha_dairy,
                "cost_price": Decimal("35.00"),
                "selling_price": Decimal("40.00"),
            },
        )
        Product.objects.get_or_create(
            name="جبنة بيضاء إسطنبولي 500جم",
            business=biz_basha,
            defaults={
                "product_category": pc_basha_dairy,
                "cost_price": Decimal("40.00"),
                "selling_price": Decimal("50.00"),
            },
        )
        Product.objects.get_or_create(
            name="كرتونة بيض أبيض (30 بيضة)",
            business=biz_basha,
            defaults={
                "product_category": pc_basha_groceries,
                "cost_price": Decimal("140.00"),
                "selling_price": Decimal("155.00"),
            },
        )

        # Business 3: صيدلية العزبي - بنها
        biz_ezaby, _ = Business.objects.get_or_create(
            name="صيدلية العزبي",
            location=banha,
            defaults={
                "description": "خدمة دوائية ورعاية صحية متكاملة على مدار 24 ساعة",
                "category": cat_pharmacies,
                "owner": owner_ezaby,
                "phone": "01033335555",
                "address": "شارع سعد زغلول - بنها",
                "avg_rating": Decimal("4.90"),
                "review_count": 210,
                "is_featured": True,
            },
        )
        create_working_hours(biz_ezaby, is_24h=True)

        pc_pharma_meds, _ = ProductCategory.objects.get_or_create(name="أدوية وفيتامينات", business=biz_ezaby, defaults={"sort_order": 1})

        Product.objects.get_or_create(
            name="بنادول إكسترا (شريط 12 أقراص)",
            business=biz_ezaby,
            defaults={
                "product_category": pc_pharma_meds,
                "cost_price": Decimal("35.00"),
                "selling_price": Decimal("42.00"),
            },
        )
        Product.objects.get_or_create(
            name="فيتامين سي 1000مجم فوار",
            business=biz_ezaby,
            defaults={
                "product_category": pc_pharma_meds,
                "cost_price": Decimal("50.00"),
                "selling_price": Decimal("65.00"),
            },
        )

        # Business 4: بيتزا ماستر - قويسنا
        biz_pizza, _ = Business.objects.get_or_create(
            name="بيتزا ماستر",
            location=quesna,
            defaults={
                "description": "بيتزا إيطالي وكريب فرنساوي وطواجن باستا",
                "category": cat_restaurants,
                "owner": owner_pizza,
                "phone": "01044446666",
                "address": "شارع الجيش - قويسنا",
                "avg_rating": Decimal("4.60"),
                "review_count": 95,
                "is_featured": True,
            },
        )
        create_working_hours(biz_pizza, datetime.time(11, 0), datetime.time(1, 0))

        pc_pizza_cat, _ = ProductCategory.objects.get_or_create(name="بيتزا إيطالي", business=biz_pizza, defaults={"sort_order": 1})
        pc_crepe_cat, _ = ProductCategory.objects.get_or_create(name="كريب ومقبلات", business=biz_pizza, defaults={"sort_order": 2})

        p_pizza_marg, _ = Product.objects.get_or_create(
            name="بيتزا مارجريتا",
            business=biz_pizza,
            defaults={
                "description": "صلصة طماطم إيطالي مع جبنة موزاريلا ورغيف ريحان",
                "product_category": pc_pizza_cat,
                "cost_price": Decimal("60.00"),
                "selling_price": Decimal("80.00"),
            },
        )
        ProductVariant.objects.get_or_create(product=p_pizza_marg, name="وسط", defaults={"cost_price": Decimal("60.00"), "selling_price": Decimal("80.00")})
        ProductVariant.objects.get_or_create(product=p_pizza_marg, name="كبير", defaults={"cost_price": Decimal("85.00"), "selling_price": Decimal("110.00")})

        Product.objects.get_or_create(
            name="كريب دجاج كرانشي",
            business=biz_pizza,
            defaults={
                "description": "قطع دجاج مقرمش مع جبنة شيدر وموزاريلا وصوص صوص",
                "product_category": pc_crepe_cat,
                "cost_price": Decimal("55.00"),
                "selling_price": Decimal("70.00"),
            },
        )

        # Business 5: مشويات البركة - عرب الرمل
        biz_baraka, _ = Business.objects.get_or_create(
            name="مشويات البركة",
            location=arab_el_raml,
            defaults={
                "description": "أششهى المشويات البلدية والكفتة والطواجن على الفحم",
                "category": cat_restaurants,
                "owner": owner_baraka,
                "phone": "01055557777",
                "address": "الطريق العام - قرية عرب الرمل",
                "avg_rating": Decimal("4.80"),
                "review_count": 140,
                "is_featured": True,
            },
        )
        create_working_hours(biz_baraka, datetime.time(12, 0), datetime.time(23, 30))

        pc_grill_cat, _ = ProductCategory.objects.get_or_create(name="مشويات على الفحم", business=biz_baraka, defaults={"sort_order": 1})

        Product.objects.get_or_create(
            name="كيلو كفتة بلدي مشوية",
            business=biz_baraka,
            defaults={
                "description": "كفتة بلدي طازجة مشوية على الفحم مع سلطة وطحينة وخبز",
                "product_category": pc_grill_cat,
                "cost_price": Decimal("320.00"),
                "selling_price": Decimal("380.00"),
            },
        )
        Product.objects.get_or_create(
            name="وجبة ربع فرخة مشوية",
            business=biz_baraka,
            defaults={
                "description": "ربع فرخة مشوية مع أرز وشوربة وسلطة",
                "product_category": pc_grill_cat,
                "cost_price": Decimal("65.00"),
                "selling_price": Decimal("80.00"),
            },
        )
        Product.objects.get_or_create(
            name="حواوشي بلدي مخصوص",
            business=biz_baraka,
            defaults={
                "description": "رغيف حواوشي بلدي باللحم المفروم والبهارات",
                "product_category": pc_grill_cat,
                "cost_price": Decimal("35.00"),
                "selling_price": Decimal("45.00"),
            },
        )

        # Business 6: مخبز وحلواني الرمل - عرب الرمل
        biz_raml_bakery, _ = Business.objects.get_or_create(
            name="مخبز وحلواني عرب الرمل",
            location=arab_el_raml,
            defaults={
                "description": "خبز طازج يومياً وحلويات شرقية وغربية للمناسبات",
                "category": cat_bakeries,
                "owner": owner_raml_bakery,
                "phone": "01066668888",
                "address": "وسط البلد - عرب الرمل",
                "avg_rating": Decimal("4.70"),
                "review_count": 60,
                "is_featured": False,
            },
        )
        create_working_hours(biz_raml_bakery, datetime.time(6, 0), datetime.time(22, 0))

        pc_sweets, _ = ProductCategory.objects.get_or_create(name="حلويات شرقية", business=biz_raml_bakery, defaults={"sort_order": 1})
        pc_bakery, _ = ProductCategory.objects.get_or_create(name="مخبوزات طازجة", business=biz_raml_bakery, defaults={"sort_order": 2})

        p_basbousa, _ = Product.objects.get_or_create(
            name="بسبوسة بالمكسرات (وزن)",
            business=biz_raml_bakery,
            defaults={
                "description": "بسبوسة بالسمن البلدي والمكسرات الطازجة",
                "product_category": pc_sweets,
                "cost_price": Decimal("80.00"),
                "selling_price": Decimal("100.00"),
            },
        )
        ProductVariant.objects.get_or_create(product=p_basbousa, name="نصف كيلو", defaults={"cost_price": Decimal("40.00"), "selling_price": Decimal("50.00")})
        ProductVariant.objects.get_or_create(product=p_basbousa, name="كيلو كامل", defaults={"cost_price": Decimal("80.00"), "selling_price": Decimal("100.00")})

        Product.objects.get_or_create(
            name="طبق فينو طازج (10 أرغفة)",
            business=biz_raml_bakery,
            defaults={
                "product_category": pc_bakery,
                "cost_price": Decimal("15.00"),
                "selling_price": Decimal("20.00"),
            },
        )

        # Business 7: سوبر ماركت التعاون - أجهور
        biz_aghour_market, _ = Business.objects.get_or_create(
            name="سوبر ماركت التعاون",
            location=aghour,
            defaults={
                "description": "توفير كافة مستلزمات الأسرة بقرية أجهور",
                "category": cat_supermarkets,
                "phone": "01077779999",
                "address": "المدخل الرئيسي - قرية أجهور",
                "avg_rating": Decimal("4.40"),
                "review_count": 45,
                "is_featured": True,
            },
        )
        create_working_hours(biz_aghour_market, datetime.time(7, 30), datetime.time(23, 0))

        pc_aghour_groc, _ = ProductCategory.objects.get_or_create(name="بقالة عامة", business=biz_aghour_market, defaults={"sort_order": 1})

        Product.objects.get_or_create(
            name="أرز مصري فاخر 1كجم",
            business=biz_aghour_market,
            defaults={
                "product_category": pc_aghour_groc,
                "cost_price": Decimal("28.00"),
                "selling_price": Decimal("32.00"),
            },
        )
        Product.objects.get_or_create(
            name="شاي العروسة 250جم",
            business=biz_aghour_market,
            defaults={
                "product_category": pc_aghour_groc,
                "cost_price": Decimal("45.00"),
                "selling_price": Decimal("52.00"),
            },
        )

        self.stdout.write(self.style.SUCCESS("[OK] Businesses, Products, Variants & Working Hours created"))

        # ----------------------------------------------------------------------
        # 5. Banners & Offers (Promotions)
        # ----------------------------------------------------------------------
        banner_global, _ = Banner.objects.get_or_create(
            title="خصومات تصل إلى 30% على مطاعم القرية",
            defaults={
                "target_type": Banner.TargetType.CATEGORY,
                "target_id": cat_restaurants.id,
                "location": None,  # Global fallback banner
                "sort_order": 1,
                "is_active": True,
            },
        )

        banner_banha, _ = Banner.objects.get_or_create(
            title="عرض خاص - التوصيل بـ 5 جنيه فقط في بنها",
            defaults={
                "target_type": Banner.TargetType.BUSINESS,
                "target_id": biz_koshary.id,
                "location": banha,
                "sort_order": 1,
                "is_active": True,
            },
        )

        offer_koshary, _ = Offer.objects.get_or_create(
            business=biz_koshary,
            title="خصم 15% على جميع الوجبات العائلية",
            defaults={
                "description": "استمتع بخصم 15% على وجبات الكشري العائلية في بنها",
                "discount_type": Offer.DiscountType.PERCENTAGE,
                "discount_value": Decimal("15.00"),
                "is_active": True,
            },
        )
        offer_koshary.products.add(p_koshary_family)

        self.stdout.write(self.style.SUCCESS("[OK] Banners & Offers created"))

        self.stdout.write(
            self.style.SUCCESS(
                "\nSuccessfully populated Phase 1A demo data!"
                "\n---------------------------------------------------"
                "\nLocations created: Banha, Aghour, Quesna, Arab El-Raml"
                "\nAdmin user:  Phone: 01001234567 | Password: AdminPassword123!"
                "\nCustomers:   Phone: 01099991111 (Banha), 01088882222 (Arab El-Raml)"
                "\nOwners:      Phone: 01011113333, 01022224444, 01033335555, etc."
                "\nDefault password for all non-admin users: password123"
                "\n---------------------------------------------------"
            )
        )
