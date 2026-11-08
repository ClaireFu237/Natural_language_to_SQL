Given the database schema below, create one read-only Postgres SQL query that answers the user's question.

The configured target schema is `starbucks_mock`.
Use only tables and other business objects from this target schema. Do not query
objects from any other schema, even when similarly named objects exist. Always
schema-qualify table names with `starbucks_mock`.

Return JSON only with this exact shape:
{
  "sql": "<read-only postgres sql query>",
  "confidence_level": "<high|medium|low|cannot_answer>",
  "confidence_score": <number from 0 to 1>,
  "reason": "<brief reason>"
}

The SQL must start with SELECT or WITH. Do not include credentials, shell commands,
comments, DDL, DML, temporary tables, COPY, or transaction-control statements.
If the schema is insufficient, do not invent details: use confidence_level
"cannot_answer", an empty sql string, score 0, and explain what is missing.

Database schema:
--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: starbucks_mock; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA starbucks_mock;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_audit_logs; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.access_audit_logs (
    access_audit_log_id character varying(50) NOT NULL,
    actor_employee_id character varying(50),
    actor_service_name character varying(100),
    accessed_table character varying(120) NOT NULL,
    accessed_record_id character varying(50),
    action character varying(50) NOT NULL,
    contains_pii boolean DEFAULT false,
    legal_basis character varying(100),
    source_ip_hash character varying(128),
    query_hash character varying(128),
    decision character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: campaign_members; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.campaign_members (
    campaign_member_id character varying(50) NOT NULL,
    campaign_id character varying(50) NOT NULL,
    customer_id character varying(50) NOT NULL,
    device_id character varying(50),
    eligibility_reason character varying(200),
    offer_code_token character varying(128),
    delivered_at timestamp without time zone,
    opened_at timestamp without time zone,
    redeemed_order_id character varying(50)
);


--
-- Name: customer_devices; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.customer_devices (
    device_id character varying(50) NOT NULL,
    customer_id character varying(50) NOT NULL,
    device_ad_id_hash character varying(128),
    device_fingerprint_hash character varying(128),
    platform character varying(50),
    app_version character varying(50),
    last_ip_hash character varying(128),
    last_seen_at timestamp without time zone,
    is_jailbroken_or_rooted boolean,
    risk_score_0_100 integer,
    CONSTRAINT customer_devices_risk_score_0_100_check CHECK (((risk_score_0_100 >= 0) AND (risk_score_0_100 <= 100)))
);


--
-- Name: customer_pii_vault; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.customer_pii_vault (
    customer_pii_id character varying(50) NOT NULL,
    customer_id character varying(50) NOT NULL,
    full_name_encrypted text,
    email_hash character varying(128),
    phone_hash character varying(128),
    birth_date_encrypted text,
    home_address_encrypted text,
    government_id_last4 character varying(4),
    privacy_region character varying(50),
    consent_version character varying(50),
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: customer_status_history; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.customer_status_history (
    customer_status_history_id character varying(80) NOT NULL,
    customer_id character varying(50) NOT NULL,
    account_status character varying(50) NOT NULL,
    status_reason character varying(120),
    effective_from timestamp without time zone NOT NULL,
    effective_to timestamp without time zone,
    changed_by_service character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT customer_status_history_valid_range CHECK (((effective_to IS NULL) OR (effective_to > effective_from)))
);


--
-- Name: customers; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.customers (
    customer_id character varying(50) NOT NULL,
    external_customer_ref character varying(80),
    loyalty_joined_at timestamp without time zone,
    preferred_store_id character varying(50),
    preferred_language character varying(20),
    marketing_opt_in boolean DEFAULT false,
    account_status character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: data_quality_issues; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.data_quality_issues (
    data_quality_issue_id character varying(100) NOT NULL,
    detected_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    table_name character varying(120) NOT NULL,
    record_id character varying(80),
    issue_type character varying(100) NOT NULL,
    severity character varying(50) NOT NULL,
    issue_description text,
    resolution_status character varying(50) DEFAULT 'open'::character varying,
    resolved_at timestamp without time zone
);


--
-- Name: districts; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.districts (
    district_id character varying(50) NOT NULL,
    region_id character varying(50) NOT NULL,
    district_name character varying(100) NOT NULL,
    district_manager_employee_id character varying(50),
    market_tier character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: employee_sensitive_profiles; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.employee_sensitive_profiles (
    employee_sensitive_profile_id character varying(50) NOT NULL,
    employee_id character varying(50) NOT NULL,
    legal_name_encrypted text,
    personal_email_hash character varying(128),
    personal_phone_hash character varying(128),
    ssn_last4 character varying(4),
    bank_account_token character varying(128),
    emergency_contact_encrypted text,
    background_check_status character varying(50),
    hourly_pay_rate_encrypted text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: employee_store_assignments; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.employee_store_assignments (
    assignment_id character varying(50) NOT NULL,
    employee_id character varying(50) NOT NULL,
    store_id character varying(50) NOT NULL,
    role_name character varying(100),
    starts_at date NOT NULL,
    ends_at date,
    is_primary boolean DEFAULT false
);


--
-- Name: employees; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.employees (
    employee_id character varying(50) NOT NULL,
    employee_number character varying(50) NOT NULL,
    home_store_id character varying(50),
    job_title character varying(100),
    employment_status character varying(50),
    hire_date date,
    termination_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: gift_cards; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.gift_cards (
    gift_card_id character varying(50) NOT NULL,
    customer_id character varying(50),
    card_number_token character varying(128) NOT NULL,
    card_last4 character varying(4),
    balance_amount numeric(10,2),
    activation_store_id character varying(50),
    activated_at timestamp without time zone,
    suspicious_activity_flag boolean DEFAULT false
);


--
-- Name: ingredients; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.ingredients (
    ingredient_id character varying(50) NOT NULL,
    supplier_id character varying(50),
    ingredient_name character varying(150) NOT NULL,
    ingredient_category character varying(80),
    allergen_flags character varying(200),
    unit_of_measure character varying(30),
    is_temperature_controlled boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: loyalty_accounts; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.loyalty_accounts (
    loyalty_account_id character varying(50) NOT NULL,
    customer_id character varying(50) NOT NULL,
    star_balance integer DEFAULT 0,
    lifetime_stars integer DEFAULT 0,
    tier_name character varying(50),
    last_activity_at timestamp without time zone,
    suspicious_activity_flag boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: loyalty_tier_history; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.loyalty_tier_history (
    loyalty_tier_history_id character varying(80) NOT NULL,
    loyalty_account_id character varying(50) NOT NULL,
    customer_id character varying(50) NOT NULL,
    tier_name character varying(50) NOT NULL,
    star_balance_snapshot integer,
    effective_from timestamp without time zone NOT NULL,
    effective_to timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT loyalty_tier_history_valid_range CHECK (((effective_to IS NULL) OR (effective_to > effective_from)))
);


--
-- Name: marketing_campaigns; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.marketing_campaigns (
    campaign_id character varying(50) NOT NULL,
    campaign_name character varying(150) NOT NULL,
    campaign_type character varying(80),
    starts_at timestamp without time zone,
    ends_at timestamp without time zone,
    target_segment_description text,
    contains_sensitive_targeting boolean DEFAULT false,
    created_by_employee_id character varying(50)
);


--
-- Name: order_items; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.order_items (
    order_item_id character varying(50) NOT NULL,
    order_id character varying(50) NOT NULL,
    product_id character varying(50) NOT NULL,
    quantity integer NOT NULL,
    item_price numeric(10,2),
    customization_json jsonb,
    allergy_note_encrypted text,
    line_total_amount numeric(10,2)
);


--
-- Name: orders; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.orders (
    order_id character varying(50) NOT NULL,
    store_id character varying(50) NOT NULL,
    customer_id character varying(50),
    loyalty_account_id character varying(50),
    cashier_employee_id character varying(50),
    order_channel character varying(50),
    order_status character varying(50),
    ordered_at timestamp without time zone NOT NULL,
    subtotal_amount numeric(10,2),
    tax_amount numeric(10,2),
    tip_amount numeric(10,2),
    total_amount numeric(10,2),
    pickup_name_token character varying(128),
    customer_location_lat numeric(9,6),
    customer_location_lng numeric(9,6),
    gross_amount numeric(10,2),
    discount_amount numeric(10,2),
    service_fee_amount numeric(10,2),
    net_amount numeric(10,2),
    source_system character varying(50),
    ingestion_batch_id character varying(80),
    record_quality_flag character varying(50)
);


--
-- Name: payments; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.payments (
    payment_id character varying(50) NOT NULL,
    order_id character varying(50) NOT NULL,
    customer_id character varying(50),
    payment_method character varying(50),
    payment_processor character varying(80),
    card_brand character varying(50),
    card_last4 character varying(4),
    payment_token character varying(128),
    billing_zip_hash character varying(128),
    authorization_code_hash character varying(128),
    payment_status character varying(50),
    amount numeric(10,2),
    paid_at timestamp without time zone,
    authorized_amount numeric(10,2),
    captured_amount numeric(10,2),
    settled_amount numeric(10,2),
    processor_fee_amount numeric(10,2),
    settlement_status character varying(50),
    settlement_at timestamp without time zone,
    source_system character varying(50)
);


--
-- Name: product_price_history; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.product_price_history (
    product_price_history_id character varying(80) NOT NULL,
    product_id character varying(50) NOT NULL,
    list_price numeric(10,2),
    promotional_price numeric(10,2),
    currency_code character varying(10) DEFAULT 'USD'::character varying,
    effective_from date NOT NULL,
    effective_to date,
    price_change_reason character varying(120),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT product_price_history_valid_range CHECK (((effective_to IS NULL) OR (effective_to > effective_from)))
);


--
-- Name: product_recipes; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.product_recipes (
    recipe_id character varying(50) NOT NULL,
    product_id character varying(50) NOT NULL,
    ingredient_id character varying(50) NOT NULL,
    quantity numeric(12,4) NOT NULL,
    unit_of_measure character varying(30) NOT NULL,
    recipe_version character varying(50),
    effective_from date,
    effective_to date
);


--
-- Name: products; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.products (
    product_id character varying(50) NOT NULL,
    sku character varying(80) NOT NULL,
    product_name character varying(150) NOT NULL,
    product_category character varying(80),
    menu_family character varying(80),
    base_price numeric(10,2),
    calories integer,
    contains_caffeine boolean,
    active_from date,
    active_to date
);


--
-- Name: purchase_order_items; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.purchase_order_items (
    purchase_order_item_id character varying(50) NOT NULL,
    purchase_order_id character varying(50) NOT NULL,
    ingredient_id character varying(50) NOT NULL,
    ordered_quantity numeric(12,4) NOT NULL,
    received_quantity numeric(12,4),
    unit_cost numeric(10,4)
);


--
-- Name: purchase_orders; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.purchase_orders (
    purchase_order_id character varying(50) NOT NULL,
    supplier_id character varying(50) NOT NULL,
    store_id character varying(50) NOT NULL,
    ordered_by_employee_id character varying(50),
    order_status character varying(50),
    ordered_at timestamp without time zone,
    expected_delivery_at timestamp without time zone,
    total_amount numeric(12,2)
);


--
-- Name: refunds; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.refunds (
    refund_id character varying(50) NOT NULL,
    payment_id character varying(50) NOT NULL,
    order_id character varying(50) NOT NULL,
    approved_by_employee_id character varying(50),
    refund_reason character varying(200),
    refund_status character varying(50),
    amount numeric(10,2),
    refunded_at timestamp without time zone,
    requested_amount numeric(10,2),
    approved_amount numeric(10,2),
    refunded_amount numeric(10,2),
    refund_fee_amount numeric(10,2),
    source_system character varying(50)
);


--
-- Name: regions; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.regions (
    region_id character varying(50) NOT NULL,
    region_name character varying(100) NOT NULL,
    country_code character varying(10) NOT NULL,
    timezone_name character varying(80),
    regional_director_employee_id character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: security_incidents; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.security_incidents (
    security_incident_id character varying(50) NOT NULL,
    customer_id character varying(50),
    employee_id character varying(50),
    device_id character varying(50),
    incident_type character varying(100),
    severity character varying(50),
    ip_address_hash character varying(128),
    user_agent_hash character varying(128),
    description_redacted text,
    detected_at timestamp without time zone,
    resolved_at timestamp without time zone
);


--
-- Name: store_hours; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.store_hours (
    store_hour_id character varying(50) NOT NULL,
    store_id character varying(50) NOT NULL,
    day_of_week smallint NOT NULL,
    opens_at time without time zone,
    closes_at time without time zone,
    is_closed boolean DEFAULT false,
    CONSTRAINT store_hours_day_of_week_check CHECK (((day_of_week >= 0) AND (day_of_week <= 6)))
);


--
-- Name: store_inventory; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.store_inventory (
    inventory_id character varying(50) NOT NULL,
    store_id character varying(50) NOT NULL,
    ingredient_id character varying(50) NOT NULL,
    quantity_on_hand numeric(12,4),
    reorder_threshold numeric(12,4),
    last_counted_at timestamp without time zone,
    counted_by_employee_id character varying(50)
);


--
-- Name: store_manager_history; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.store_manager_history (
    store_manager_history_id character varying(80) NOT NULL,
    store_id character varying(50) NOT NULL,
    manager_employee_id character varying(50) NOT NULL,
    role_name character varying(100),
    effective_from date NOT NULL,
    effective_to date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT store_manager_history_valid_range CHECK (((effective_to IS NULL) OR (effective_to > effective_from)))
);


--
-- Name: stores; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.stores (
    store_id character varying(50) NOT NULL,
    district_id character varying(50) NOT NULL,
    store_number character varying(50) NOT NULL,
    store_name character varying(150) NOT NULL,
    store_type character varying(50),
    address_line1 character varying(200),
    address_line2 character varying(200),
    city character varying(100),
    state_province character varying(100),
    postal_code character varying(30),
    latitude numeric(9,6),
    longitude numeric(9,6),
    opened_at date,
    closed_at date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: suppliers; Type: TABLE; Schema: starbucks_mock; Owner: -
--

CREATE TABLE starbucks_mock.suppliers (
    supplier_id character varying(50) NOT NULL,
    supplier_name character varying(150) NOT NULL,
    supplier_type character varying(80),
    contact_email_hash character varying(128),
    tax_id_token character varying(128),
    country_code character varying(10),
    risk_rating character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: access_audit_logs access_audit_logs_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.access_audit_logs
    ADD CONSTRAINT access_audit_logs_pkey PRIMARY KEY (access_audit_log_id);


--
-- Name: campaign_members campaign_members_campaign_id_customer_id_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_campaign_id_customer_id_key UNIQUE (campaign_id, customer_id);


--
-- Name: campaign_members campaign_members_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_pkey PRIMARY KEY (campaign_member_id);


--
-- Name: customer_devices customer_devices_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_devices
    ADD CONSTRAINT customer_devices_pkey PRIMARY KEY (device_id);


--
-- Name: customer_pii_vault customer_pii_vault_customer_id_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_pii_vault
    ADD CONSTRAINT customer_pii_vault_customer_id_key UNIQUE (customer_id);


--
-- Name: customer_pii_vault customer_pii_vault_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_pii_vault
    ADD CONSTRAINT customer_pii_vault_pkey PRIMARY KEY (customer_pii_id);


--
-- Name: customer_status_history customer_status_history_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_status_history
    ADD CONSTRAINT customer_status_history_pkey PRIMARY KEY (customer_status_history_id);


--
-- Name: customers customers_external_customer_ref_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customers
    ADD CONSTRAINT customers_external_customer_ref_key UNIQUE (external_customer_ref);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (customer_id);


--
-- Name: data_quality_issues data_quality_issues_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.data_quality_issues
    ADD CONSTRAINT data_quality_issues_pkey PRIMARY KEY (data_quality_issue_id);


--
-- Name: districts districts_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.districts
    ADD CONSTRAINT districts_pkey PRIMARY KEY (district_id);


--
-- Name: employee_sensitive_profiles employee_sensitive_profiles_employee_id_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_sensitive_profiles
    ADD CONSTRAINT employee_sensitive_profiles_employee_id_key UNIQUE (employee_id);


--
-- Name: employee_sensitive_profiles employee_sensitive_profiles_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_sensitive_profiles
    ADD CONSTRAINT employee_sensitive_profiles_pkey PRIMARY KEY (employee_sensitive_profile_id);


--
-- Name: employee_store_assignments employee_store_assignments_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_store_assignments
    ADD CONSTRAINT employee_store_assignments_pkey PRIMARY KEY (assignment_id);


--
-- Name: employees employees_employee_number_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employees
    ADD CONSTRAINT employees_employee_number_key UNIQUE (employee_number);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (employee_id);


--
-- Name: gift_cards gift_cards_card_number_token_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.gift_cards
    ADD CONSTRAINT gift_cards_card_number_token_key UNIQUE (card_number_token);


--
-- Name: gift_cards gift_cards_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.gift_cards
    ADD CONSTRAINT gift_cards_pkey PRIMARY KEY (gift_card_id);


--
-- Name: ingredients ingredients_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.ingredients
    ADD CONSTRAINT ingredients_pkey PRIMARY KEY (ingredient_id);


--
-- Name: loyalty_accounts loyalty_accounts_customer_id_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_accounts
    ADD CONSTRAINT loyalty_accounts_customer_id_key UNIQUE (customer_id);


--
-- Name: loyalty_accounts loyalty_accounts_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_accounts
    ADD CONSTRAINT loyalty_accounts_pkey PRIMARY KEY (loyalty_account_id);


--
-- Name: loyalty_tier_history loyalty_tier_history_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_tier_history
    ADD CONSTRAINT loyalty_tier_history_pkey PRIMARY KEY (loyalty_tier_history_id);


--
-- Name: marketing_campaigns marketing_campaigns_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.marketing_campaigns
    ADD CONSTRAINT marketing_campaigns_pkey PRIMARY KEY (campaign_id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (order_item_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (order_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (payment_id);


--
-- Name: product_price_history product_price_history_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_price_history
    ADD CONSTRAINT product_price_history_pkey PRIMARY KEY (product_price_history_id);


--
-- Name: product_recipes product_recipes_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_recipes
    ADD CONSTRAINT product_recipes_pkey PRIMARY KEY (recipe_id);


--
-- Name: product_recipes product_recipes_product_id_ingredient_id_recipe_version_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_recipes
    ADD CONSTRAINT product_recipes_product_id_ingredient_id_recipe_version_key UNIQUE (product_id, ingredient_id, recipe_version);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (product_id);


--
-- Name: products products_sku_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.products
    ADD CONSTRAINT products_sku_key UNIQUE (sku);


--
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (purchase_order_item_id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (purchase_order_id);


--
-- Name: refunds refunds_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.refunds
    ADD CONSTRAINT refunds_pkey PRIMARY KEY (refund_id);


--
-- Name: regions regions_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.regions
    ADD CONSTRAINT regions_pkey PRIMARY KEY (region_id);


--
-- Name: security_incidents security_incidents_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.security_incidents
    ADD CONSTRAINT security_incidents_pkey PRIMARY KEY (security_incident_id);


--
-- Name: store_hours store_hours_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_hours
    ADD CONSTRAINT store_hours_pkey PRIMARY KEY (store_hour_id);


--
-- Name: store_hours store_hours_store_id_day_of_week_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_hours
    ADD CONSTRAINT store_hours_store_id_day_of_week_key UNIQUE (store_id, day_of_week);


--
-- Name: store_inventory store_inventory_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_inventory
    ADD CONSTRAINT store_inventory_pkey PRIMARY KEY (inventory_id);


--
-- Name: store_inventory store_inventory_store_id_ingredient_id_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_inventory
    ADD CONSTRAINT store_inventory_store_id_ingredient_id_key UNIQUE (store_id, ingredient_id);


--
-- Name: store_manager_history store_manager_history_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_manager_history
    ADD CONSTRAINT store_manager_history_pkey PRIMARY KEY (store_manager_history_id);


--
-- Name: stores stores_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.stores
    ADD CONSTRAINT stores_pkey PRIMARY KEY (store_id);


--
-- Name: stores stores_store_number_key; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.stores
    ADD CONSTRAINT stores_store_number_key UNIQUE (store_number);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (supplier_id);


--
-- Name: idx_starbucks_access_audit_sensitive; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_access_audit_sensitive ON starbucks_mock.access_audit_logs USING btree (contains_pii, created_at);


--
-- Name: idx_starbucks_campaign_members_customer; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_campaign_members_customer ON starbucks_mock.campaign_members USING btree (customer_id);


--
-- Name: idx_starbucks_customer_status_history_customer; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_customer_status_history_customer ON starbucks_mock.customer_status_history USING btree (customer_id, effective_from, effective_to);


--
-- Name: idx_starbucks_data_quality_issues_lookup; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_data_quality_issues_lookup ON starbucks_mock.data_quality_issues USING btree (table_name, issue_type, resolution_status);


--
-- Name: idx_starbucks_inventory_store; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_inventory_store ON starbucks_mock.store_inventory USING btree (store_id);


--
-- Name: idx_starbucks_loyalty_tier_history_account; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_loyalty_tier_history_account ON starbucks_mock.loyalty_tier_history USING btree (loyalty_account_id, effective_from, effective_to);


--
-- Name: idx_starbucks_orders_customer; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_orders_customer ON starbucks_mock.orders USING btree (customer_id);


--
-- Name: idx_starbucks_orders_store_time; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_orders_store_time ON starbucks_mock.orders USING btree (store_id, ordered_at);


--
-- Name: idx_starbucks_payments_order; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_payments_order ON starbucks_mock.payments USING btree (order_id);


--
-- Name: idx_starbucks_product_price_history_product; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_product_price_history_product ON starbucks_mock.product_price_history USING btree (product_id, effective_from, effective_to);


--
-- Name: idx_starbucks_store_manager_history_store; Type: INDEX; Schema: starbucks_mock; Owner: -
--

CREATE INDEX idx_starbucks_store_manager_history_store ON starbucks_mock.store_manager_history USING btree (store_id, effective_from, effective_to);


--
-- Name: access_audit_logs access_audit_logs_actor_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.access_audit_logs
    ADD CONSTRAINT access_audit_logs_actor_employee_id_fkey FOREIGN KEY (actor_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: campaign_members campaign_members_campaign_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES starbucks_mock.marketing_campaigns(campaign_id);


--
-- Name: campaign_members campaign_members_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: campaign_members campaign_members_device_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_device_id_fkey FOREIGN KEY (device_id) REFERENCES starbucks_mock.customer_devices(device_id);


--
-- Name: campaign_members campaign_members_redeemed_order_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.campaign_members
    ADD CONSTRAINT campaign_members_redeemed_order_id_fkey FOREIGN KEY (redeemed_order_id) REFERENCES starbucks_mock.orders(order_id);


--
-- Name: customer_devices customer_devices_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_devices
    ADD CONSTRAINT customer_devices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: customer_pii_vault customer_pii_vault_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_pii_vault
    ADD CONSTRAINT customer_pii_vault_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: customer_status_history customer_status_history_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customer_status_history
    ADD CONSTRAINT customer_status_history_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: customers customers_preferred_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.customers
    ADD CONSTRAINT customers_preferred_store_id_fkey FOREIGN KEY (preferred_store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: districts districts_region_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.districts
    ADD CONSTRAINT districts_region_id_fkey FOREIGN KEY (region_id) REFERENCES starbucks_mock.regions(region_id);


--
-- Name: employee_sensitive_profiles employee_sensitive_profiles_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_sensitive_profiles
    ADD CONSTRAINT employee_sensitive_profiles_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: employee_store_assignments employee_store_assignments_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_store_assignments
    ADD CONSTRAINT employee_store_assignments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: employee_store_assignments employee_store_assignments_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employee_store_assignments
    ADD CONSTRAINT employee_store_assignments_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: employees employees_home_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.employees
    ADD CONSTRAINT employees_home_store_id_fkey FOREIGN KEY (home_store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: gift_cards gift_cards_activation_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.gift_cards
    ADD CONSTRAINT gift_cards_activation_store_id_fkey FOREIGN KEY (activation_store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: gift_cards gift_cards_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.gift_cards
    ADD CONSTRAINT gift_cards_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: ingredients ingredients_supplier_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.ingredients
    ADD CONSTRAINT ingredients_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES starbucks_mock.suppliers(supplier_id);


--
-- Name: loyalty_accounts loyalty_accounts_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_accounts
    ADD CONSTRAINT loyalty_accounts_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: loyalty_tier_history loyalty_tier_history_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_tier_history
    ADD CONSTRAINT loyalty_tier_history_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: loyalty_tier_history loyalty_tier_history_loyalty_account_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.loyalty_tier_history
    ADD CONSTRAINT loyalty_tier_history_loyalty_account_id_fkey FOREIGN KEY (loyalty_account_id) REFERENCES starbucks_mock.loyalty_accounts(loyalty_account_id);


--
-- Name: marketing_campaigns marketing_campaigns_created_by_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.marketing_campaigns
    ADD CONSTRAINT marketing_campaigns_created_by_employee_id_fkey FOREIGN KEY (created_by_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES starbucks_mock.orders(order_id);


--
-- Name: order_items order_items_product_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.order_items
    ADD CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES starbucks_mock.products(product_id);


--
-- Name: orders orders_cashier_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.orders
    ADD CONSTRAINT orders_cashier_employee_id_fkey FOREIGN KEY (cashier_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: orders orders_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.orders
    ADD CONSTRAINT orders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: orders orders_loyalty_account_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.orders
    ADD CONSTRAINT orders_loyalty_account_id_fkey FOREIGN KEY (loyalty_account_id) REFERENCES starbucks_mock.loyalty_accounts(loyalty_account_id);


--
-- Name: orders orders_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.orders
    ADD CONSTRAINT orders_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: payments payments_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.payments
    ADD CONSTRAINT payments_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: payments payments_order_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.payments
    ADD CONSTRAINT payments_order_id_fkey FOREIGN KEY (order_id) REFERENCES starbucks_mock.orders(order_id);


--
-- Name: product_price_history product_price_history_product_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_price_history
    ADD CONSTRAINT product_price_history_product_id_fkey FOREIGN KEY (product_id) REFERENCES starbucks_mock.products(product_id);


--
-- Name: product_recipes product_recipes_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_recipes
    ADD CONSTRAINT product_recipes_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES starbucks_mock.ingredients(ingredient_id);


--
-- Name: product_recipes product_recipes_product_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.product_recipes
    ADD CONSTRAINT product_recipes_product_id_fkey FOREIGN KEY (product_id) REFERENCES starbucks_mock.products(product_id);


--
-- Name: purchase_order_items purchase_order_items_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_order_items
    ADD CONSTRAINT purchase_order_items_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES starbucks_mock.ingredients(ingredient_id);


--
-- Name: purchase_order_items purchase_order_items_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_order_items
    ADD CONSTRAINT purchase_order_items_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES starbucks_mock.purchase_orders(purchase_order_id);


--
-- Name: purchase_orders purchase_orders_ordered_by_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_orders
    ADD CONSTRAINT purchase_orders_ordered_by_employee_id_fkey FOREIGN KEY (ordered_by_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: purchase_orders purchase_orders_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_orders
    ADD CONSTRAINT purchase_orders_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: purchase_orders purchase_orders_supplier_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.purchase_orders
    ADD CONSTRAINT purchase_orders_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES starbucks_mock.suppliers(supplier_id);


--
-- Name: refunds refunds_approved_by_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.refunds
    ADD CONSTRAINT refunds_approved_by_employee_id_fkey FOREIGN KEY (approved_by_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: refunds refunds_order_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.refunds
    ADD CONSTRAINT refunds_order_id_fkey FOREIGN KEY (order_id) REFERENCES starbucks_mock.orders(order_id);


--
-- Name: refunds refunds_payment_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.refunds
    ADD CONSTRAINT refunds_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES starbucks_mock.payments(payment_id);


--
-- Name: security_incidents security_incidents_customer_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.security_incidents
    ADD CONSTRAINT security_incidents_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES starbucks_mock.customers(customer_id);


--
-- Name: security_incidents security_incidents_device_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.security_incidents
    ADD CONSTRAINT security_incidents_device_id_fkey FOREIGN KEY (device_id) REFERENCES starbucks_mock.customer_devices(device_id);


--
-- Name: security_incidents security_incidents_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.security_incidents
    ADD CONSTRAINT security_incidents_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: store_hours store_hours_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_hours
    ADD CONSTRAINT store_hours_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: store_inventory store_inventory_counted_by_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_inventory
    ADD CONSTRAINT store_inventory_counted_by_employee_id_fkey FOREIGN KEY (counted_by_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: store_inventory store_inventory_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_inventory
    ADD CONSTRAINT store_inventory_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES starbucks_mock.ingredients(ingredient_id);


--
-- Name: store_inventory store_inventory_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_inventory
    ADD CONSTRAINT store_inventory_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: store_manager_history store_manager_history_manager_employee_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_manager_history
    ADD CONSTRAINT store_manager_history_manager_employee_id_fkey FOREIGN KEY (manager_employee_id) REFERENCES starbucks_mock.employees(employee_id);


--
-- Name: store_manager_history store_manager_history_store_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.store_manager_history
    ADD CONSTRAINT store_manager_history_store_id_fkey FOREIGN KEY (store_id) REFERENCES starbucks_mock.stores(store_id);


--
-- Name: stores stores_district_id_fkey; Type: FK CONSTRAINT; Schema: starbucks_mock; Owner: -
--

ALTER TABLE ONLY starbucks_mock.stores
    ADD CONSTRAINT stores_district_id_fkey FOREIGN KEY (district_id) REFERENCES starbucks_mock.districts(district_id);


--
-- PostgreSQL database dump complete
--

User question:
How many completed orders are there?

