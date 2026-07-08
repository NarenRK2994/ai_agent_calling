import json
import re
from pathlib import Path


ROOT = Path(r"E:\invotec_erp_dev\ai_agent_calling")
METADATA_DIR = ROOT / "data" / "metadata"


TABLE_DESCRIPTIONS = {
    "AP_CHECKS_ALL": "Payment instrument header table for Oracle Accounts Payable disbursements. Each record represents a payment document or electronic payment issued to a supplier and captures settlement details, bank information, payment status, remittance attributes, supplier references, and reconciliation data used in the procure-to-pay cycle.",
    "AP_INVOICE_DISTRIBUTIONS_ALL": "Invoice accounting distribution table for Oracle Accounts Payable. Each record represents an accounting or charge distribution derived from an invoice line, matched purchase order distribution, tax calculation, or prepayment application and is used to drive expense recognition, accrual accounting, project charging, and General Ledger posting.",
    "AP_INVOICE_LINES_ALL": "Invoice line detail table for Oracle Accounts Payable. Each record represents a supplier invoice line such as an item, tax, freight, miscellaneous charge, or prepayment application and supports invoice matching, charge allocation, receiving verification, project coding, and downstream accounting distributions.",
    "AP_INVOICE_PAYMENTS_ALL": "Invoice payment application table for Oracle Accounts Payable. Each record represents a payment event applied to a supplier invoice and links the invoice, payment instrument, accounting dates, gains or losses, and settlement amounts used in payment accounting and audit history.",
    "AP_INVOICES_ALL": "Supplier invoice header table for Oracle Accounts Payable. Each record represents an invoice, debit memo, credit memo, expense report, or prepayment entered for a supplier and holds the supplier reference, payment attributes, accounting context, approval status, tax information, and purchase order linkage used throughout the procure-to-pay process.",
    "AP_PAYMENT_SCHEDULES_ALL": "Installment and due-date schedule table for Oracle Accounts Payable. Each record represents a planned payment installment for a supplier invoice and is used by Payment Process Requests to determine due dates, discounts, holds, remittance instructions, and remaining liability.",
    "AP_SUPPLIERS": "Supplier master reference used by the current metadata set for Oracle Accounts Payable. Each record represents a supplier and provides the business identity needed to associate invoices and payments with the supplier master, although this environment also uses Oracle Purchasing supplier tables such as PO_VENDORS.",
    "AR_CASH_RECEIPTS_ALL": "Cash receipt header table for Oracle Accounts Receivable. Each record represents a customer receipt, remittance, miscellaneous receipt, or reversal event and captures the amount, customer reference, receipt method, bank processing, status, and accounting context used in the order-to-cash cycle.",
    "AR_RECEIVABLE_APPLICATIONS_ALL": "Receipt application detail table for Oracle Accounts Receivable. Each record represents the application, unapplication, on-account activity, chargeback, or reversal of a cash receipt against a customer transaction or payment schedule and provides the accounting trail for receipt application history.",
    "CST_ITEM_COSTS": "Item cost table for Oracle Cost Management. Each record represents the cost of an inventory item for a specific organization and cost type and stores the material, resource, overhead, and rolled-up cost components used in valuation, inventory accounting, and cost analysis.",
    "HZ_CUST_ACCOUNTS": "Customer account master table in Oracle Trading Community Architecture. Each record represents a commercial customer account associated with a party and is used by Accounts Receivable to control billing relationships, account ownership, and customer transaction processing.",
    "HZ_PARTIES": "Core party master table in Oracle Trading Community Architecture. Each record represents a person, organization, or group used as the shared business identity for customers, suppliers, banks, and other trading partners across Oracle EBS modules.",
    "MTL_MATERIAL_TRANSACTIONS": "Inventory movement transaction history table for Oracle Inventory. Each record represents a material transaction such as receipt, issue, transfer, adjustment, return, or WIP movement and provides the operational and costing detail required for inventory visibility, valuation, and audit tracking.",
    "MTL_SYSTEM_ITEMS_B": "Base item master table for Oracle Inventory. Each record represents an inventory item definition within an organization and controls planning, purchasing, costing, shipping, receiving, service, and inventory behavior used across supply chain processes.",
    "MTL_SYSTEM_ITEMS_TL": "Translated item description table for Oracle Inventory. Each record stores language-specific descriptive text for an inventory item and supports multilingual item inquiry, reporting, and user interface presentation by organization.",
    "MTL_TRANSACTION_TYPES": "Inventory transaction type setup table for Oracle Inventory. Each record defines a transaction type used to classify material movements, associate a transaction action and source type, and control how inventory transactions are interpreted by the application.",
    "PO_VENDORS": "Supplier master table used by Oracle Purchasing and referenced throughout Procure to Pay. Each record represents a supplier entity and stores supplier identity, payment defaults, tax reporting information, control flags, and relationships used by purchasing, payables, and supplier management processes.",
    "PO_VENDOR_SITES_ALL": "Supplier site master table for Oracle Purchasing and Accounts Payable. Each record represents a supplier site such as purchasing, pay, remit-to, or RFQ site and stores address, payment, tax, and operating-unit-specific controls used when transacting with suppliers.",
    "RA_CUSTOMER_TRX_ALL": "Accounts Receivable transaction header table. Each record represents an invoice, debit memo, credit memo, chargeback, or bill receivable transaction and captures customer billing references, transaction dates, source details, ledger context, and order-to-cash processing attributes.",
    "RA_CUSTOMER_TRX_LINES_ALL": "Accounts Receivable transaction line table. Each record represents a billed line, tax line, freight line, or charge line belonging to a receivables transaction and provides item, quantity, pricing, tax, and revenue recognition detail for billing and accounting.",
}


BUSINESS_QUESTIONS = {
    "AP_CHECKS_ALL": [
        "Show supplier payments issued during a date range.",
        "List voided, stopped, or cancelled payment documents.",
        "Find checks that have not yet cleared the bank.",
        "Show payments issued to a specific supplier or supplier site.",
        "Display bank account and payment method details for disbursements.",
        "Find payments created by a specific payment batch or payment run.",
        "Show cleared amount and clearing date for reconciled payments.",
        "Identify high-value supplier payments above a business threshold.",
    ],
    "AP_INVOICE_DISTRIBUTIONS_ALL": [
        "Show accounting distributions created for a supplier invoice.",
        "Find invoice distributions matched to a purchase order distribution.",
        "Display expense, accrual, and tax distribution amounts by invoice.",
        "Show invoice distributions pending accounting or posting.",
        "Find project-related invoice distributions by project or task.",
        "Analyze invoice price variance and exchange rate variance amounts.",
        "List distributions created from prepayment applications.",
        "Show distributions by line type and General Ledger account.",
    ],
    "AP_INVOICE_LINES_ALL": [
        "Show invoice line details for a supplier invoice.",
        "List item, tax, freight, and miscellaneous lines by invoice.",
        "Find invoice lines matched to purchase orders or receipts.",
        "Show invoice lines with quantity, unit price, and amount.",
        "Identify expense report lines missing receipts or justification.",
        "List invoice lines charged to projects or awards.",
        "Find cancelled or discarded invoice lines.",
        "Show invoice lines awaiting distribution generation or approval.",
    ],
    "AP_INVOICE_PAYMENTS_ALL": [
        "Show payment history for a supplier invoice.",
        "Trace a payment document back to the invoices it settled.",
        "List payment applications posted during a period.",
        "Show payment gains, losses, discounts, and accounting dates.",
        "Find reversed invoice payment applications.",
        "Display partial payments made against an invoice.",
        "Show payment records by supplier, bank account, or operating unit.",
        "Identify invoices paid by a specific check or payment instruction.",
    ],
    "AP_INVOICES_ALL": [
        "Show unpaid supplier invoices by supplier and due date.",
        "Find invoices pending approval or validation.",
        "List invoices matched to purchase orders.",
        "Show cancelled invoices and cancellation amounts.",
        "Find invoices received but not yet fully paid.",
        "Display invoice aging by supplier or operating unit.",
        "Show invoices with tax amounts and payment status.",
        "Identify high-value invoices above an approval threshold.",
        "List prepayment invoices and their remaining balances.",
        "Show invoice headers with supplier site and remittance details.",
    ],
    "AP_PAYMENT_SCHEDULES_ALL": [
        "Show due dates and remaining amounts for supplier invoices.",
        "Find invoices eligible for payment discounts.",
        "List payment schedules currently on hold.",
        "Show future-dated supplier payment obligations.",
        "Identify invoices with multiple scheduled installments.",
        "Display payment priority and payment method by invoice schedule.",
        "Find overdue payment schedules by supplier.",
        "Show remittance instructions attached to payment schedules.",
    ],
    "AP_SUPPLIERS": [
        "Show supplier master details used by Accounts Payable.",
        "List invoices associated with a supplier.",
        "Find supplier names by internal supplier identifier.",
        "Show suppliers with invoice activity in the current period.",
        "Identify suppliers with unpaid invoices.",
        "Display supplier records referenced by Payables transactions.",
        "Find suppliers used in invoice and payment reporting.",
        "Show supplier master records requiring reconciliation with purchasing supplier tables.",
    ],
    "AR_CASH_RECEIPTS_ALL": [
        "Show customer cash receipts entered during a date range.",
        "Find unapplied or partially applied cash receipts.",
        "List reversed or NSF receipts with reversal details.",
        "Show cash receipts by customer, receipt method, or bank account.",
        "Identify high-value receipts above a business threshold.",
        "Display receipt status and remittance information.",
        "Find receipts awaiting confirmation or clearing.",
        "Show miscellaneous receipts and their accounting attributes.",
    ],
    "AR_RECEIVABLE_APPLICATIONS_ALL": [
        "Show how customer receipts were applied to invoices.",
        "Find unapplied or reversed receipt applications.",
        "Display earned and unearned discount amounts taken on applications.",
        "Show receipt applications posted during a period.",
        "Trace a receipt application to the related customer transaction.",
        "Identify on-account and chargeback application activity.",
        "Show tax, freight, and charge portions applied to receivables.",
        "List applications by customer, receipt, or transaction status.",
    ],
    "CST_ITEM_COSTS": [
        "Show item cost by organization and cost type.",
        "Compare material, resource, and overhead cost components.",
        "Find item costs used for inventory valuation.",
        "Show cost records updated by a cost rollup or cost update.",
        "Identify items with zero or missing item cost.",
        "Display standard or average cost details for an item.",
        "Find item costs for a specific inventory organization.",
        "Analyze cost changes across items and cost types.",
    ],
    "HZ_CUST_ACCOUNTS": [
        "Show customer account details and account status.",
        "Trace customer accounts to receivables transactions.",
        "Find customer accounts for a party record.",
        "Show billing accounts used for a specific customer transaction.",
        "Identify customer accounts with recent invoice activity.",
        "List customer accounts by account number or account name.",
        "Display customer accounts by operating unit or business classification.",
        "Find accounts associated with a specific bill-to customer reference.",
    ],
    "HZ_PARTIES": [
        "Show party master details for customers or suppliers.",
        "Find the party record associated with a customer account.",
        "List organizations or persons by party name or number.",
        "Show party records referenced by receivables customers.",
        "Identify parties used across multiple Oracle modules.",
        "Display party master information for reporting and integration.",
        "Find duplicate or similar party names for review.",
        "Trace a party to downstream customer account usage.",
    ],
    "MTL_MATERIAL_TRANSACTIONS": [
        "Show material transaction history for an inventory item.",
        "Find inventory issues, receipts, transfers, and adjustments by date.",
        "Display transactions by organization, subinventory, and locator.",
        "Show transaction cost, quantity, and source reference details.",
        "Find transactions by transaction type or source type.",
        "Trace inventory movements related to a purchase receipt or work order.",
        "Identify costed versus uncosted material transactions.",
        "Show transfer transactions between organizations or subinventories.",
    ],
    "MTL_SYSTEM_ITEMS_B": [
        "Show item master setup for an inventory organization.",
        "Find items enabled for purchasing, inventory, and customer orders.",
        "Display planning, costing, and receiving controls for an item.",
        "Show item attributes used in shipping and inventory transactions.",
        "Find items by item number, description, or category segment.",
        "Identify items that are inactive or end-dated.",
        "Show items with serial, lot, or locator control enabled.",
        "Display item master records used in costing and transaction history.",
    ],
    "MTL_SYSTEM_ITEMS_TL": [
        "Show translated item descriptions for an inventory item.",
        "Find multilingual descriptions by language and organization.",
        "Display long item descriptions for reporting or integrations.",
        "Show which items have translated descriptions in a given language.",
        "Trace translated descriptions back to the base item master.",
        "Find missing translated descriptions for active items.",
        "List language-specific descriptions for customer-facing reporting.",
        "Compare source language and translated language item text.",
    ],
    "MTL_TRANSACTION_TYPES": [
        "Show configured inventory transaction types.",
        "Find the transaction type used for a material movement.",
        "Display transaction action and source type for each transaction type.",
        "Identify disabled or end-dated transaction types.",
        "Show user-defined transaction types created by the business.",
        "List transaction types used in inventory adjustments or transfers.",
        "Find transaction types that require locator control.",
        "Display setup details for inventory transaction classification.",
    ],
    "PO_VENDORS": [
        "Show supplier master records and supplier classification details.",
        "Find suppliers used on Payables invoices.",
        "Display supplier payment defaults and withholding settings.",
        "Show suppliers by supplier number, name, or party reference.",
        "Identify suppliers on hold for purchasing or payment.",
        "List suppliers by type, tax reporting status, or payment priority.",
        "Show active and inactive supplier records.",
        "Find suppliers associated with a specific party or parent supplier.",
    ],
    "PO_VENDOR_SITES_ALL": [
        "Show supplier site details for purchasing and payment processing.",
        "Find pay sites and purchasing sites for a supplier.",
        "Display address and remittance information by supplier site.",
        "Show supplier sites used on Payables invoices.",
        "Identify supplier sites on payment hold.",
        "List supplier sites by operating unit and payment method.",
        "Show remit-to site setup and banking attributes.",
        "Find inactive or future-dated supplier sites.",
    ],
    "RA_CUSTOMER_TRX_ALL": [
        "Show Accounts Receivable invoices and credit memos by customer.",
        "Find customer transactions by transaction number and date.",
        "Display receivables transactions by bill-to customer account.",
        "Show transactions created from a specific batch source.",
        "Identify completed, posted, or reversed receivables transactions.",
        "List customer invoices with payment terms and due date context.",
        "Show bill-to and ship-to customer references on a transaction.",
        "Find receivables transactions associated with an order or interface source.",
    ],
    "RA_CUSTOMER_TRX_LINES_ALL": [
        "Show line-level billing details for a customer transaction.",
        "Find item, tax, freight, and charge lines on an AR invoice.",
        "Display quantities, unit prices, and extended amounts by line.",
        "Show revenue-related details for invoice lines.",
        "Find transaction lines for a specific inventory item.",
        "Identify tax-exempt or tax-recoverable invoice lines.",
        "Show lines linked to previous transactions or credits.",
        "Display ship-to references and operational attributes by line.",
    ],
}


RELATIONSHIPS = [
    ("AP_INVOICES_ALL", "INVOICE_ID", "AP_INVOICE_LINES_ALL", "INVOICE_ID"),
    ("AP_INVOICES_ALL", "INVOICE_ID", "AP_INVOICE_DISTRIBUTIONS_ALL", "INVOICE_ID"),
    ("AP_INVOICES_ALL", "INVOICE_ID", "AP_PAYMENT_SCHEDULES_ALL", "INVOICE_ID"),
    ("AP_INVOICES_ALL", "INVOICE_ID", "AP_INVOICE_PAYMENTS_ALL", "INVOICE_ID"),
    ("AP_CHECKS_ALL", "CHECK_ID", "AP_INVOICE_PAYMENTS_ALL", "CHECK_ID"),
    ("PO_VENDORS", "VENDOR_ID", "AP_INVOICES_ALL", "VENDOR_ID"),
    ("PO_VENDOR_SITES_ALL", "VENDOR_SITE_ID", "AP_INVOICES_ALL", "VENDOR_SITE_ID"),
    ("PO_VENDORS", "VENDOR_ID", "PO_VENDOR_SITES_ALL", "VENDOR_ID"),
    ("AP_SUPPLIERS", "VENDOR_ID", "AP_INVOICES_ALL", "VENDOR_ID"),
    ("HZ_PARTIES", "PARTY_ID", "HZ_CUST_ACCOUNTS", "PARTY_ID"),
    ("HZ_CUST_ACCOUNTS", "CUST_ACCOUNT_ID", "RA_CUSTOMER_TRX_ALL", "BILL_TO_CUSTOMER_ID"),
    ("RA_CUSTOMER_TRX_ALL", "CUSTOMER_TRX_ID", "RA_CUSTOMER_TRX_LINES_ALL", "CUSTOMER_TRX_ID"),
    ("RA_CUSTOMER_TRX_ALL", "CUSTOMER_TRX_ID", "AR_RECEIVABLE_APPLICATIONS_ALL", "APPLIED_CUSTOMER_TRX_ID"),
    ("AR_CASH_RECEIPTS_ALL", "CASH_RECEIPT_ID", "AR_RECEIVABLE_APPLICATIONS_ALL", "CASH_RECEIPT_ID"),
    ("MTL_SYSTEM_ITEMS_B", "INVENTORY_ITEM_ID, ORGANIZATION_ID", "MTL_SYSTEM_ITEMS_TL", "INVENTORY_ITEM_ID, ORGANIZATION_ID"),
    ("MTL_SYSTEM_ITEMS_B", "INVENTORY_ITEM_ID, ORGANIZATION_ID", "MTL_MATERIAL_TRANSACTIONS", "INVENTORY_ITEM_ID, ORGANIZATION_ID"),
    ("MTL_SYSTEM_ITEMS_B", "INVENTORY_ITEM_ID, ORGANIZATION_ID", "CST_ITEM_COSTS", "INVENTORY_ITEM_ID, ORGANIZATION_ID"),
    ("MTL_TRANSACTION_TYPES", "TRANSACTION_TYPE_ID", "MTL_MATERIAL_TRANSACTIONS", "TRANSACTION_TYPE_ID"),
]


FOREIGN_KEY_TARGETS = {
    "ACCTS_PAY_CODE_COMBINATION_ID": "the Accounts Payable liability account combination in General Ledger.",
    "ACCOUNTING_EVENT_ID": "the Subledger Accounting event that generated accounting for the transaction.",
    "ACCOUNTING_RULE_ID": "the accounting rule that controls revenue recognition timing.",
    "APPLIED_CUSTOMER_TRX_ID": "the receivables transaction header being settled by the application.",
    "APPLIED_CUSTOMER_TRX_LINE_ID": "the receivables transaction line being settled by the application.",
    "APPLIED_PAYMENT_SCHEDULE_ID": "the payment schedule being affected by the receipt application.",
    "ASSET_BOOK_TYPE_CODE": "the Oracle Assets book used for capitalization tracking.",
    "ASSET_CATEGORY_ID": "the Oracle Assets category used for capitalization or asset tracking.",
    "AWARD_ID": "the award or grant associated with the transaction.",
    "AWT_GROUP_ID": "the withholding tax group applied to the transaction.",
    "BANK_ACCOUNT_ID": "the internal bank account used to process the payment or receipt.",
    "BANK_ACCOUNT_NAME": "the bank account name used for settlement or remittance.",
    "BANK_NUM": "the bank number associated with the settlement account.",
    "BATCH_ID": "the import, entry, or processing batch that grouped the transaction.",
    "BATCH_SOURCE_ID": "the transaction source used to create the receivables document.",
    "BILL_TO_CONTACT_ID": "the bill-to contact associated with the customer transaction.",
    "BILL_TO_CUSTOMER_ID": "the bill-to customer account referenced by the transaction.",
    "BILL_TO_LOCATION_ID": "the bill-to location used for supplier site or customer billing purposes.",
    "BILL_TO_SITE_USE_ID": "the bill-to site use associated with the transaction.",
    "BUYER_ID": "the buyer responsible for the item or purchasing relationship.",
    "CASH_RECEIPT_HISTORY_ID": "the cash receipt history event linked to the application.",
    "CASH_RECEIPT_ID": "the cash receipt header associated with the application or receipt activity.",
    "CHECK_ID": "the payment document or electronic payment record associated with the settlement.",
    "CODE_COMBINATION_ID": "the General Ledger account combination associated with the accounting entry.",
    "COST_GROUP_ID": "the inventory cost group used for valuation and accounting.",
    "COST_TYPE_ID": "the cost type that defines how item cost is valued or analyzed.",
    "CREDITED_INVOICE_ID": "the original invoice that was credited by this transaction.",
    "CUST_ACCOUNT_ID": "the customer account in Trading Community Architecture.",
    "CUST_TRX_TYPE_ID": "the receivables transaction type that controls accounting and processing behavior.",
    "CUSTOMER_BANK_ACCOUNT_ID": "the customer bank account used for receipt processing.",
    "CUSTOMER_RECEIPT_REFERENCE": "the customer-provided reference captured on the receipt.",
    "CUSTOMER_TRX_ID": "the receivables transaction header to which the record belongs.",
    "CUSTOMER_TRX_LINE_ID": "the receivables transaction line identified by the record.",
    "DEFAULT_DIST_CCID": "the default General Ledger account combination used when creating invoice distributions.",
    "DEPARTMENT_ID": "the inventory or operational department associated with the transaction.",
    "DISTRIBUTION_SET_ID": "the predefined distribution set used to default accounting information.",
    "DIST_CODE_COMBINATION_ID": "the General Ledger distribution account charged by the transaction.",
    "DOC_SEQUENCE_ID": "the document sequencing definition used to assign the transaction number.",
    "EXTERNAL_BANK_ACCOUNT_ID": "the external supplier or customer bank account used for settlement.",
    "GL_DATE": "the accounting date used when the transaction is posted to General Ledger.",
    "INTEREST_HEADER_ID": "the related interest invoice or interest charge header.",
    "INTERFACE_LINE_CONTEXT": "the source interface context used to populate the receivables line.",
    "INTERFACE_LINE_ID": "the source interface line that created the transaction.",
    "INVENTORY_ITEM_ID": "the inventory item master record associated with the transaction.",
    "INVOICE_DISTRIBUTION_ID": "the invoice accounting distribution record.",
    "INVOICE_ID": "the supplier invoice header associated with the line, distribution, schedule, or payment.",
    "INVOICE_PAYMENT_ID": "the unique invoice payment application record.",
    "ITEM_CATALOG_GROUP_ID": "the item catalog group used to classify the item.",
    "LEGAL_ENTITY_ID": "the legal entity responsible for the transaction.",
    "LINE_NUMBER": "the business sequence number of the line within the document.",
    "LOCATION_ID": "the address or inventory location referenced by the record.",
    "LOCATOR_ID": "the inventory locator used for the material transaction.",
    "MOVE_ORDER_LINE_ID": "the move order line that generated the inventory transaction.",
    "ORGANIZATION_ID": "the inventory organization or operating organization that owns the record.",
    "PARTY_ID": "the Trading Community Architecture party associated with the record.",
    "PARTY_SITE_ID": "the party site associated with the supplier, customer, or payment record.",
    "PAYMENT_SCHEDULE_ID": "the receivables payment schedule referenced by the application.",
    "PO_DISTRIBUTION_ID": "the purchase order distribution referenced by the invoice activity.",
    "PO_HEADER_ID": "the purchase order header associated with the transaction.",
    "PO_LINE_ID": "the purchase order line associated with the transaction.",
    "PO_LINE_LOCATION_ID": "the purchase order shipment line associated with the transaction.",
    "PO_RELEASE_ID": "the purchase order release associated with the transaction.",
    "PROGRAM_APPLICATION_ID": "the Oracle application that submitted the concurrent program update.",
    "PROGRAM_ID": "the concurrent program that last updated the record.",
    "PROJECT_ID": "the project charged by the transaction.",
    "RCV_TRANSACTION_ID": "the receiving transaction associated with the invoice match or inventory event.",
    "REASON_ID": "the reason code definition explaining why the transaction occurred.",
    "RECEIPT_METHOD_ID": "the receipt method controlling customer receipt processing.",
    "REFERENCE_ID": "the referenced business entity linked to the transaction.",
    "REQUESTER_ID": "the employee or user who requested the expense or purchase-related transaction.",
    "REQUEST_ID": "the concurrent request that created or last updated the record.",
    "SOLD_TO_CUSTOMER_ID": "the sold-to customer account associated with the receivables transaction.",
    "SOLD_TO_SITE_USE_ID": "the sold-to site use associated with the transaction.",
    "SHIP_TO_CONTACT_ID": "the ship-to contact associated with the transaction.",
    "SHIP_TO_CUSTOMER_ID": "the ship-to customer account associated with the transaction.",
    "SHIP_TO_LOCATION_ID": "the ship-to location used for logistics or receiving control.",
    "SHIP_TO_SITE_USE_ID": "the ship-to site use associated with the transaction.",
    "SUBINVENTORY_CODE": "the inventory subinventory where the material transaction occurred.",
    "TASK_ID": "the task charged by the project-related transaction.",
    "TERMS_ID": "the payment terms definition applied to the transaction.",
    "TRANSACTION_ACTION_ID": "the inventory transaction action that determines how stock is affected.",
    "TRANSACTION_SOURCE_TYPE_ID": "the source type that explains what business process created the inventory transaction.",
    "TRANSACTION_TYPE_ID": "the inventory transaction type that classifies the material movement.",
    "VENDOR_ID": "the supplier master record associated with the transaction.",
    "VENDOR_SITE_ID": "the supplier site associated with the transaction.",
    "WAREHOUSE_ID": "the warehouse organization used for shipping or inventory processing.",
}


TABLE_ALIASES = {
    "AP_CHECKS_ALL": "supplier payment",
    "AP_INVOICE_DISTRIBUTIONS_ALL": "invoice distribution",
    "AP_INVOICE_LINES_ALL": "invoice line",
    "AP_INVOICE_PAYMENTS_ALL": "invoice payment",
    "AP_INVOICES_ALL": "supplier invoice",
    "AP_PAYMENT_SCHEDULES_ALL": "invoice payment schedule",
    "AP_SUPPLIERS": "supplier",
    "AR_CASH_RECEIPTS_ALL": "cash receipt",
    "AR_RECEIVABLE_APPLICATIONS_ALL": "receipt application",
    "CST_ITEM_COSTS": "item cost record",
    "HZ_CUST_ACCOUNTS": "customer account",
    "HZ_PARTIES": "party",
    "MTL_MATERIAL_TRANSACTIONS": "material transaction",
    "MTL_SYSTEM_ITEMS_B": "inventory item",
    "MTL_SYSTEM_ITEMS_TL": "translated item description",
    "MTL_TRANSACTION_TYPES": "transaction type",
    "PO_VENDORS": "supplier",
    "PO_VENDOR_SITES_ALL": "supplier site",
    "RA_CUSTOMER_TRX_ALL": "receivables transaction",
    "RA_CUSTOMER_TRX_LINES_ALL": "receivables transaction line",
}


MANUAL_REVIEW_TABLES = []


def normalize_column_name(name: str) -> str:
    return re.sub(r"#\d+$", "", name)


def spaced(name: str) -> str:
    return normalize_column_name(name).replace("_", " ").lower()


def make_relationship_map():
    rel_map = {}
    for parent_table, parent_join, child_table, child_join in RELATIONSHIPS:
        rel_map.setdefault(parent_table, []).append(
            {"table": child_table, "join": child_join, "relationship_type": "child"}
        )
        rel_map.setdefault(child_table, []).append(
            {"table": parent_table, "join": parent_join, "relationship_type": "parent"}
        )
    return rel_map


RELATIONSHIP_MAP = make_relationship_map()


def audit_description(col: str) -> str | None:
    if col == "CREATED_BY":
        return "User identifier for the person or process that created the record."
    if col == "CREATION_DATE":
        return "Date and time when the record was created."
    if col == "LAST_UPDATED_BY":
        return "User identifier for the person or process that last updated the record."
    if col == "LAST_UPDATE_DATE":
        return "Date and time when the record was last updated."
    if col == "LAST_UPDATE_LOGIN":
        return "Login session identifier that performed the last update."
    if col == "REQUEST_ID":
        return "Concurrent request identifier for the program run that created or updated the record."
    if col == "PROGRAM_APPLICATION_ID":
        return "Oracle application identifier for the concurrent program that last updated the record."
    if col == "PROGRAM_ID":
        return "Concurrent program identifier for the process that last updated the record."
    if col == "PROGRAM_UPDATE_DATE":
        return "Date and time when the concurrent program last updated the record."
    return None


def primary_key_description(table: str, col: str, primary_keys: set[str]) -> str | None:
    table_alias = TABLE_ALIASES.get(table, "record")
    if col not in primary_keys:
        return None
    if col == "INVOICE_ID":
        return "Unique system-generated identifier for the supplier invoice. Used to relate the invoice header to lines, distributions, payment schedules, and payment history."
    if col == "CUSTOMER_TRX_ID":
        return "Unique system-generated identifier for the receivables transaction. Used to relate the transaction header to transaction lines, schedules, and receipt applications."
    if col == "CASH_RECEIPT_ID":
        return "Unique system-generated identifier for the cash receipt. Used to track receipt lifecycle, applications, reversals, and accounting."
    if col == "CHECK_ID":
        return "Unique system-generated identifier for the supplier payment document or electronic payment."
    if col == "INVOICE_PAYMENT_ID":
        return "Unique system-generated identifier for the invoice payment application record."
    if col == "INVOICE_DISTRIBUTION_ID":
        return "Unique system-generated identifier for the invoice accounting distribution."
    if col == "CUST_ACCOUNT_ID":
        return "Unique system-generated identifier for the customer account in Trading Community Architecture."
    if col == "PARTY_ID":
        return "Unique system-generated identifier for the party record shared across Oracle EBS modules."
    if col == "TRANSACTION_ID":
        return "Unique system-generated identifier for the inventory material transaction."
    if col == "TRANSACTION_TYPE_ID":
        return "Unique system-generated identifier for the inventory transaction type definition."
    if col == "VENDOR_ID":
        return f"Unique system-generated identifier for the {table_alias}. Used to relate supplier transactions, sites, invoices, and payments."
    if col == "VENDOR_SITE_ID":
        return "Unique system-generated identifier for the supplier site used by purchasing and payables transactions."
    if col == "INVENTORY_ITEM_ID":
        return f"Unique system-generated identifier for the {table_alias}. Used together with organization context to relate item setup, translated descriptions, costs, and transaction history."
    if col == "LINE_NUMBER":
        return f"Business sequence number identifying the {table_alias} within its parent document."
    return None


def explicit_description(table: str, col: str) -> str | None:
    explicit = {
        "ACCOUNTING_DATE": "Accounting date used to recognize the transaction in Subledger Accounting and General Ledger.",
        "ACCTS_PAY_CODE_COMBINATION_ID": "Liability account combination charged for the supplier invoice or payment accounting entry.",
        "AMOUNT": "Monetary amount recorded for the transaction in the transaction currency.",
        "AMOUNT_PAID": "Total amount already paid against the supplier invoice.",
        "APPROVAL_READY_FLAG": "Indicates whether the transaction is ready to enter the approval workflow.",
        "APPROVAL_STATUS": "Current approval status of the transaction within Oracle workflow or validation processing.",
        "AUTHORIZED_BY": "User or approver responsible for authorizing the transaction.",
        "BASE_AMOUNT": "Functional currency amount derived from the entered transaction amount.",
        "BANK_CHARGE_BEARER": "Indicates which party bears bank charges associated with the payment or receipt settlement.",
        "BILL_TO_CUSTOMER_ID": "Customer account used as the bill-to party on the receivables transaction.",
        "CHECK_DIGITS": "Check digits used to validate the business reference or external account number.",
        "CHECK_DATE": "Date on which the payment document was issued.",
        "CHECK_NUMBER": "Business payment document number assigned to the check or payment instrument.",
        "CITY": "City component of the supplier, customer, or remittance address.",
        "COUNTRY": "Country component of the supplier, customer, or remittance address.",
        "COUNTY": "County or administrative district component of the address.",
        "CURRENCY_CODE": "Currency code in which the transaction is denominated.",
        "DESCRIPTION": "Free-text business description entered to explain the purpose or content of the transaction.",
        "DISCOUNT_AMOUNT_TAKEN": "Discount amount taken at the time of payment settlement.",
        "DUE_DATE": "Date on which payment is due based on payment terms and schedule calculation.",
        "EMAIL_ADDRESS": "Email address used for supplier, customer, or party communication.",
        "EXCHANGE_DATE": "Date used to derive the foreign currency conversion rate.",
        "EXCHANGE_RATE": "Exchange rate used to convert the foreign currency transaction to functional currency.",
        "EXCHANGE_RATE_TYPE": "Conversion rate type used to derive the exchange rate for the transaction.",
        "EXCLUDE_FREIGHT_FROM_DISCOUNT": "Indicates whether freight charges are excluded when payment discounts are calculated.",
        "FOB_POINT": "Free On Board point that determines when ownership or shipping responsibility transfers.",
        "GL_DATE": "Accounting date used when posting the transaction to General Ledger.",
        "GOODS_RECEIVED_DATE": "Date on which the goods or services were received.",
        "GROSS_AMOUNT": "Gross scheduled amount before discount or settlement adjustments.",
        "HOLD_FLAG": "Indicates whether the transaction or schedule is on hold from further processing.",
        "HOLD_REASON": "Reason explaining why the supplier site, invoice, or payment record was placed on hold.",
        "INCOME_TAX_REGION": "Income tax region used for statutory reporting or withholding processing.",
        "INVOICE_AMOUNT": "Total invoice amount entered before payment settlement.",
        "INVOICE_AMOUNT_LIMIT": "Maximum invoice amount allowed based on the supplier or site control setup.",
        "INVOICE_CURRENCY_CODE": "Currency in which the supplier invoice was entered.",
        "INVOICE_DATE": "Date printed on the supplier invoice or receivables document.",
        "INVOICE_NUM": "Supplier invoice number entered by the supplier and used as the primary business reference.",
        "INVOICE_TYPE_LOOKUP_CODE": "Lookup code identifying the invoice type, such as standard invoice, credit memo, debit memo, or prepayment.",
        "ITEM_COST": "Total item cost for the organization and cost type after combining all cost components.",
        "LANGUAGE": "Language code for the translated value stored in the row.",
        "LONG_DESCRIPTION": "Long-form description used when the standard description is not sufficient for business reporting or inquiry.",
        "MATCH_STATUS_FLAG": "Indicates the current matching status of the invoice distribution against purchasing or receiving records.",
        "MATCH_OPTION": "Matching control option that determines whether invoice matching is performed at purchase order or receipt level.",
        "MERCHANT_REFERENCE": "Reference supplied by the merchant for the card or expense transaction.",
        "ORG_ID": "Operating unit identifier that owns the transaction in a multi-org Oracle EBS environment.",
        "ORIG_SYSTEM_REFERENCE": "Reference to the originating source system record used during integration or conversion.",
        "PARTY_NUMBER": "Business reference number assigned to the Trading Community party.",
        "PARTY_SITE_ID": "Party site associated with the supplier, customer, or payment record.",
        "PAYMENT_CROSS_RATE": "Cross-currency rate used when invoice and payment currencies differ.",
        "PAYMENT_CURRENCY_CODE": "Currency used when payment is made or settled.",
        "PAYMENT_METHOD_CODE": "Payment method used to settle the transaction.",
        "PAYMENT_METHOD_LOOKUP_CODE": "Lookup code identifying the method used to settle the transaction.",
        "PAYMENT_NUM": "Sequence number identifying the payment event or installment against the document.",
        "PAYMENT_PRIORITY": "Processing priority used when selecting transactions for payment.",
        "PAYMENT_REASON_CODE": "Business reason code associated with the payment or settlement instruction.",
        "PAYMENT_STATUS_FLAG": "Indicates whether the invoice or schedule is unpaid, partially paid, fully paid, or otherwise settled.",
        "PO_DISTRIBUTION_ID": "Purchase order distribution referenced by the matched transaction.",
        "PO_HEADER_ID": "Purchase order header referenced by the matched transaction.",
        "PO_LINE_ID": "Purchase order line referenced by the matched transaction.",
        "PRIMARY_UOM_CODE": "Primary unit of measure used to control inventory balances and transactions for the item.",
        "PROJECT_ACCOUNTING_CONTEXT": "Project accounting context used to derive project-related charging and accounting behavior.",
        "PROVINCE": "Province or regional component of the supplier, customer, or remittance address.",
        "RECEIPT_DATE": "Date on which the customer receipt was entered or received.",
        "RECEIPT_NUMBER": "Business receipt number assigned to the customer receipt.",
        "REMIT_TO_SUPPLIER_SITE": "Supplier site to which payment remittance is directed.",
        "SETTLEMENT_PRIORITY": "Priority used by payment processing to determine the order of settlement.",
        "SET_OF_BOOKS_ID": "Ledger identifier in which accounting entries are recorded.",
        "SHIP_VIA": "Shipping method or carrier reference associated with the transaction or customer account.",
        "SOURCE": "Source that created the transaction, such as manual entry, import, or another Oracle process.",
        "SOURCE_LANG": "Original language from which the translated value was derived.",
        "STATE": "State or province code component of the supplier, customer, or remittance address.",
        "STATUS": "Current processing status of the transaction within the Oracle application flow.",
        "STATUS_LOOKUP_CODE": "Lookup code identifying the current status of the record.",
        "TAX_AMOUNT": "Total tax amount calculated for the transaction.",
        "TAX_RATE": "Tax rate applied to calculate the tax amount.",
        "TERMS_DATE": "Date used as the basis for calculating payment due dates and discount dates.",
        "TERMS_DATE_BASIS": "Basis used to determine which date should drive payment term calculation.",
        "TOTAL_TAX_AMOUNT": "Total tax liability associated with the transaction.",
        "TRANSACTION_DATE": "Date on which the inventory material movement was recorded.",
        "TRANSACTION_QUANTITY": "Quantity moved by the inventory transaction in the entered transaction unit of measure.",
        "TRANSACTION_REFERENCE": "User-entered or system-generated reference describing the source of the material transaction.",
        "TRANSACTION_TYPE_NAME": "Business name of the inventory transaction type.",
        "TRX_DATE": "Transaction date of the receivables document.",
        "TRX_BUSINESS_CATEGORY": "Business transaction category used by tax or compliance processing.",
        "TYPE_1099": "1099 reporting classification assigned to the supplier transaction for statutory reporting.",
        "TRX_NUMBER": "Business transaction number assigned to the receivables document.",
        "UNIT_PRICE": "Unit price used to calculate the transaction amount.",
        "USER_DEFINED_FISC_CLASS": "User-defined fiscal classification applied for tax determination and reporting.",
        "USSGL_TRX_CODE_CONTEXT": "Context value used to interpret the USSGL transaction code for federal reporting.",
        "USSGL_TRANSACTION_CODE_CONTEXT": "Context value used to interpret the USSGL transaction code for federal reporting.",
        "VAT_CODE": "Tax classification code applied to the transaction.",
        "VENDOR_NAME": "Business name of the supplier.",
        "VENDOR_SITE_CODE": "Business code identifying the supplier site.",
        "WFAPPROVAL_STATUS": "Workflow approval status recorded for the transaction or line.",
        "ZIP": "Postal code component of the supplier, customer, or remittance address.",
    }
    return explicit.get(col)


def generic_id_description(col: str) -> str:
    target = FOREIGN_KEY_TARGETS.get(col)
    if target:
        return f"Foreign key referencing {target[0].lower() + target[1:]}" if target.startswith("the ") else f"Foreign key referencing {target}"

    entity = spaced(col[:-3])
    return f"System-generated identifier for the related {entity} record."


def generic_date_description(col: str) -> str:
    mapping = {
        "CANCELLED_DATE": "Date on which the transaction was cancelled.",
        "CLEARED_DATE": "Date on which the payment or receipt cleared the bank.",
        "CLOSE_DATE": "Date on which the record or process was closed.",
        "DEF_ACCTG_END_DATE": "End date of the deferred accounting recognition period.",
        "DEF_ACCTG_START_DATE": "Start date of the deferred accounting recognition period.",
        "DEPOSIT_DATE": "Date on which the receipt was deposited to the bank.",
        "DISCOUNT_DATE": "Date through which the current discount amount remains available.",
        "EARLIEST_SETTLEMENT_DATE": "Earliest date on which the transaction can be settled.",
        "END_DATE_ACTIVE": "Date on which the record becomes inactive.",
        "END_EXPENSE_DATE": "End date of the expense period covered by the line or distribution.",
        "FUTURE_PAY_DUE_DATE": "Future dated payment due date used for settlement scheduling.",
        "GOODS_RECEIVED_DATE": "Date on which goods or services were received.",
        "INVOICE_RECEIVED_DATE": "Date on which Accounts Payable received the supplier invoice.",
        "ISSUE_DATE": "Date on which the document or instrument was issued.",
        "POSTMARK_DATE": "Postmark date associated with mailing or receipt handling.",
        "RELEASED_DATE": "Date on which the payment or hold was released.",
        "REVERSAL_DATE": "Date on which the transaction or application was reversed.",
        "RULE_END_DATE": "End date for the accounting or billing rule application.",
        "RULE_START_DATE": "Start date for the accounting or billing rule application.",
        "SALES_ORDER_DATE": "Date on which the referenced sales order was created or booked.",
        "START_DATE_ACTIVE": "Date from which the record becomes active.",
        "START_EXPENSE_DATE": "Start date of the expense period covered by the line or distribution.",
        "STOPPED_DATE": "Date on which the payment was stopped.",
        "TERMS_DATE": "Date used to derive payment term due dates and discounts.",
        "TREASURY_PAY_DATE": "Date on which treasury processing settled the payment.",
        "VOID_DATE": "Date on which the payment document was voided.",
    }
    if col in mapping:
        return mapping[col]
    return f"Business date associated with {spaced(col[:-5])}."


def generic_flag_description(col: str) -> str:
    return f"Indicates whether {spaced(col[:-5])} applies to the record."


def generic_amount_description(col: str) -> str:
    words = spaced(col[:-7])
    return f"Monetary amount representing {words} for the transaction."


def generic_rate_description(col: str) -> str:
    words = spaced(col[:-5])
    return f"Rate used to calculate or value {words} for the transaction."


def generic_code_description(col: str) -> str:
    words = spaced(col[:-5])
    return f"Lookup or classification code identifying {words} for the record."


def generic_num_description(col: str) -> str:
    words = spaced(col[:-4])
    return f"Business number used to identify or sequence {words}."


def generic_name_description(col: str) -> str:
    words = spaced(col[:-5])
    return f"Business name associated with {words}."


def generic_type_description(col: str) -> str:
    words = spaced(col[:-5])
    return f"Type classification used to control {words} processing."


def generic_status_description(col: str) -> str:
    words = spaced(col[:-7])
    return f"Status value showing the current processing state of {words}."


def generic_quantity_description(col: str) -> str:
    words = spaced(col[:-9])
    return f"Quantity associated with {words} for the transaction."


def generic_desc(table: str, col: str, primary_keys: set[str]) -> str:
    base = normalize_column_name(col)
    if re.fullmatch(r"ATTRIBUTE\d+", base):
        return "Descriptive Flexfield available for customer-specific business information."
    if re.fullmatch(r"GLOBAL_ATTRIBUTE\d+", base):
        return "Global Descriptive Flexfield used for country-specific or global business requirements."
    if re.fullmatch(r"SEGMENT\d+", base):
        seg_no = re.findall(r"\d+", base)[0]
        if table == "PO_VENDORS" and base == "SEGMENT1":
            return "Primary supplier number segment used as the business supplier identifier."
        if table == "MTL_SYSTEM_ITEMS_B" and base == "SEGMENT1":
            return "Primary item number segment used as the core business item identifier."
        if table == "MTL_SYSTEM_ITEMS_B":
            return f"Additional item key flexfield segment {seg_no} used to build the full item number or item classification."
        return f"Flexfield segment {seg_no} used to capture business classification or numbering information."

    audit = audit_description(base)
    if audit:
        return audit

    explicit = explicit_description(table, base)
    if explicit:
        return explicit

    primary = primary_key_description(table, base, primary_keys)
    if primary:
        return primary

    if base.endswith("_ID"):
        return generic_id_description(base)
    if re.fullmatch(r"ADDRESS_LINE\d+", base):
        line_no = re.findall(r"\d+", base)[0]
        return f"Address line {line_no} of the supplier, customer, or remittance address."
    if base.endswith("_DATE"):
        return generic_date_description(base)
    if base.endswith("_AT"):
        return f"Date and time when {spaced(base[:-3])} occurred."
    if base.endswith("_BY"):
        return f"User or person responsible for {spaced(base[:-3])}."
    if base.endswith("_FLAG"):
        return generic_flag_description(base)
    if base.endswith("_AMOUNT"):
        return generic_amount_description(base)
    if base.endswith("_AMT"):
        return f"Monetary amount recorded for {spaced(base[:-4])}."
    if base.endswith("_RATE"):
        return generic_rate_description(base)
    if base.endswith("_CODE"):
        return generic_code_description(base)
    if base.endswith("_CONTEXT"):
        return f"Context value used to interpret or derive {spaced(base[:-8])}."
    if base.endswith("_CATEGORY"):
        return f"Business category assigned to {spaced(base[:-9])}."
    if base.endswith("_CLASS"):
        return f"Classification assigned to {spaced(base[:-6])}."
    if base.endswith("_GROUP"):
        return f"Grouping value used to classify or process {spaced(base[:-6])}."
    if base.endswith("_LIMIT"):
        return f"Maximum permitted value for {spaced(base[:-6])}."
    if base.endswith("_PRIORITY"):
        return "Priority used to control processing of the record."
    if base.endswith("_REFERENCE"):
        return f"Business reference captured for {spaced(base[:-10])}."
    if base.endswith("_TEXT"):
        return f"Detailed text associated with {spaced(base[:-5])}."
    if base.endswith("_VALUE"):
        return f"Stored value associated with {spaced(base[:-6])}."
    if base.endswith("_POINT"):
        return f"Point or location reference used for {spaced(base[:-6])}."
    if base.endswith("_REASON"):
        return f"Business reason captured for {spaced(base[:-7])}."
    if base.endswith("_ALLOWED"):
        return f"Allowed number or value for {spaced(base[:-8])}."
    if base.endswith("_BASIS"):
        return f"Basis used to calculate or derive {spaced(base[:-6])}."
    if base.endswith("_NUM") or base.endswith("_NUMBER"):
        return generic_num_description(base)
    if base.endswith("_NAME"):
        return generic_name_description(base)
    if base.endswith("_TYPE"):
        return generic_type_description(base)
    if base.endswith("_STATUS"):
        return generic_status_description(base)
    if "ROUNDING" in base:
        return f"Rounding adjustment associated with {spaced(base)}."
    if "MERCHANT" in base:
        return f"Merchant-related attribute captured for card or expense transaction processing: {spaced(base)}."
    if "REMITTANCE_MESSAGE" in base:
        return "Remittance advice message communicated to the supplier during payment processing."
    if "RETAINED_AMOUNT" in base:
        return "Retainage amount associated with the transaction and any remaining retained balance."
    if "AMOUNT_REMAINING" in base:
        return "Remaining monetary balance that has not yet been settled or applied."
    if "TOLERANCE" in base:
        return f"Tolerance threshold used to control {spaced(base)}."
    if "REFERENCE" in base:
        return "Reference value used for integration, reconciliation, or business traceability."
    if "USSGL" in base:
        return "USSGL-related attribute used for U.S. federal accounting and reporting."
    if "1099" in base:
        return "1099-related tax reporting attribute used for statutory supplier reporting."
    if "UPGRADE" in base:
        return "Legacy upgrade or migration attribute preserved from conversion processing."
    if "QUANTITY" in base:
        return generic_quantity_description(base)
    if base.endswith("_PRICE"):
        return f"Price amount used for {spaced(base[:-6])} valuation or billing."
    if base.endswith("_PERCENT") or "PERCENT" in base:
        return f"Percentage value used to calculate {spaced(base)}."
    if base.endswith("_UOM") or base.endswith("_UOM_CODE") or "UNIT_OF_MEASURE" in base:
        return f"Unit of measure used for {spaced(base.replace('_UOM_CODE', '').replace('_UOM', '').replace('UNIT_OF_MEASURE', 'quantity'))}."
    if base.endswith("_DESCRIPTION"):
        return f"Descriptive text explaining {spaced(base[:-12])}."
    if base.startswith("MRC_"):
        return f"Multiple Reporting Currency attribute for {spaced(base[4:])}."
    if base.startswith("REFERENCE_") or base.startswith("REFERENCE_KEY"):
        return "Reference value used for integration, audit tracking, or cross-system linkage."
    if base.startswith("DOC_LINE_ID_"):
        return "Document line reference used by tax, integration, or source document tracking."
    if base in {"DESCRIPTION", "COMMENTS", "JUSTIFICATION"}:
        return "Free-text explanation entered to document the business purpose of the record."
    if base == "LANGUAGE":
        return "Language code associated with the translated or displayed value."
    if base == "SOURCE_LANG":
        return "Original language from which the translated value was derived."
    if base == "ENABLED_FLAG":
        return "Indicates whether the record is currently enabled for transaction processing."
    if base == "SUMMARY_FLAG":
        return "Indicates whether the record is a summary-level definition rather than a transactional detail record."
    if base == "STATUS":
        return "Current processing status of the record within the Oracle application flow."

    table_alias = TABLE_ALIASES.get(table, "record")
    return f"Business attribute of the {table_alias} used for Oracle EBS transaction processing, control, or reporting."


def enrich_column_description(table: str, col: str, primary_keys: set[str]) -> str:
    desc = generic_desc(table, col, primary_keys)
    if "#" in col:
        desc += " Source metadata export included this as a repeated occurrence of the same business attribute."
    return desc


def dedupe_relationships(rels):
    seen = set()
    deduped = []
    for rel in rels:
        key = (rel["table"], rel["join"], rel["relationship_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(rel)
    return deduped


def main():
    files = sorted([p for p in METADATA_DIR.glob("*.json") if p.name != ".gitkeep"])
    files_updated = 0
    columns_enriched = 0
    relationships_improved = 0
    business_questions_generated = 0
    duplicate_column_tables = []

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        table = payload["table"]
        payload["description"] = TABLE_DESCRIPTIONS.get(
            table,
            f"Oracle EBS metadata table for {table.replace('_', ' ').title()} used for enterprise transaction processing and reporting.",
        )
        primary_keys = {part.strip() for part in payload.get("primary_key", "").split(",") if part.strip()}

        seen_cols = set()
        has_duplicate_like = False
        for column in payload.get("columns", []):
            col_name = column["name"]
            if col_name in seen_cols:
                has_duplicate_like = True
            seen_cols.add(col_name)
            if "#" in col_name:
                has_duplicate_like = True
            column["description"] = enrich_column_description(table, col_name, primary_keys)
            columns_enriched += 1

        if has_duplicate_like:
            duplicate_column_tables.append(table)

        relationships = RELATIONSHIP_MAP.get(table, payload.get("relationships", []))
        relationships = dedupe_relationships(relationships)
        payload["relationships"] = relationships
        relationships_improved += len(relationships)

        questions = BUSINESS_QUESTIONS.get(table, payload.get("business_questions", []))
        payload["business_questions"] = questions
        business_questions_generated += len(questions)

        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        files_updated += 1

    manual_review = set(duplicate_column_tables)
    if (METADATA_DIR / "ap_suppliers.json").exists():
        manual_review.add("AP_SUPPLIERS")

    report = {
        "files_updated": files_updated,
        "columns_enriched": columns_enriched,
        "relationships_improved": relationships_improved,
        "business_questions_generated": business_questions_generated,
        "manual_review_tables": sorted(manual_review),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
