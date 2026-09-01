/**
 * LVE Plan Validation App Script
 *
 * This is meant to be a container-bound script, with timezone set locally (required). All
 * rules use setAllowInvalid(true) - advisory warnings, not hard blocks.
 */

const SSHEET = SpreadsheetApp.getActiveSpreadsheet();

const PERIOD_TYPES = ['Year', 'Month', 'Week', 'Day'];

const PAY_CATEGORIES = [
  'Housing',
  'Auto',
  'Diet',
  'Health & Self-Care',
  'Clothing',
  'Learning',
  'Electronics, Apps, & Comms',
  'Furnishings & Textiles',
  'Kitchen',
  'Cleaning',
  'Other Household Costs',
  'Transport & Travel',
  'Finance & Legal',
  'Recreation',
  'Other Costs',
];

const CPI_CATEGORIES = [
  // Shelter
  'Rent',
  "Tenants' insurance premiums",
  "Tenants' maintenance, repairs and other expenses",
  'Electricity',
  'Water',
  'Natural gas',
  'Fuel oil and other fuels',
  // Food
  'Food',
  'Food purchased from stores',
  'Food purchased from restaurants',
  // Household Operations
  'Telephone services',
  'Internet access services',
  'Postal and other communications services',
  'Laundry detergents and soaps',
  'Detergents and rinse agents for dish washing',
  'Household cleaning and polishing products',
  'Bleach and other household chemical products',
  'Fabric softener',
  'Household paper supplies',
  'Stationery',
  'Plastic and aluminum foil supplies',
  'Other household supplies',
  'Other household services',
  'Financial services',
  // Household Furnishing and Equpment
  'Upholstered furniture',
  'Wooden furniture',
  'Other furniture',
  'Window Coverings',
  'Bedding and other household textiles',
  'Cooking appliances',
  'Refrigerators and freezers',
  'Laundry and dishwashing appliances',
  'Other household appliances',
  'Non-electric kitchen utensils, tableware and cookware',
  'Household tools (including lawn, garden and snow removal equipment)',
  'Other household equipment',
  // Clothing
  "Men's clothing",
  "Men's footwear (excluding athletic)",
  'Athletic footwear',
  'Clothing accessories',
  'Watches',
  'Clothing material, notions and services',
  // Transportation
  'Gasoline',
  'Passenger vehicle parts, accessories and supplies',
  'Passenger vehicle maintenance and repair services',
  'Passenger vehicle insurance premiums',
  'Passenger vehicle registration fees',
  "Drivers' licences",
  'Parking fees',
  'City bus and subway transportation',
  'Air transportation',
  // Health
  'Prescribed medicines (excluding medicinal cannabis)',
  'Non-prescribed medicines',
  'Eye care goods',
  'Other health care goods',
  'Eye care services',
  'Dental care services',
  'Other health care services',
  // Personal Care
  'Personal soap',
  'Toiletry items and cosmetics',
  'Oral-hygiene products',
  'Other personal care supplies and equipment',
  'Personal care services',
  // Recreation, Education, and Reading
  'Computer equipment, software and supplies',
  'Multipurpose digital devices',
  'Recreational services',
  'School textbooks and supplies',
  'Other lessons, courses and education services',
  'Books and reading material (excluding textbooks)',
  'Alcoholic beverages purchased from stores',
];

// -----------------------------------------------------------------------------
// Formula Fragments
//
// Range starts are anchored ($A$2:$A) so the comparison window doesn't
// shift as the formula fills down each row.
// -----------------------------------------------------------------------------

/** Converts a column number ot its A1-style letter code. */
function alphaCode(colPos) {
  let code = '';
  while (colPos > 0) {
    code = String.fromCharCode(65 + ((colPos - 1) % 26)) + code;
    colPos = Math.floor((colPos - 1) / 26);
  }
  return code;
}

function nonBlankFormula(col) {
  return `TRIM(${alphaCode(col)}2)<>""`;
}

function uniqueFormula(col) {
  const c = alphaCode(col);
  return `COUNTIF($${c}$2:$${c}, ${c}2)=1`;
}

const numberFormula = (col, min) => {
  const cell = `${alphaCode(col)}2`;
  return `AND(ISNUMBER(${cell}), ${cell}>=${min})`;
};

/** Combines one or more boolean formula fragments into a single formula. */
function formulaRule(fragments) {
  const body = fragments.length === 1 ? fragments[0] : `AND(${fragments.join(',')})`;
  return SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(`=${body}`)
    .setAllowInvalid(true)
    .build();
}

// -----------------------------------------------------------------------------
// Rule Builders: (columnIndex) => DataValidation | null
// -----------------------------------------------------------------------------

const uniqueNonBlank = (col) => formulaRule([nonBlankFormula(col), uniqueFormula(col)]);
const nonBlank = (col) => formulaRule([nonBlankFormula(col)]);
const numberMin = (min) => (col) => formulaRule([numberFormula(col, min)]);
const dropdown = (list) => () =>
  SpreadsheetApp.newDataValidation()
    .requireValueInList(list, true)
    .setAllowInvalid(true)
    .build();
const date = () =>
  SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(true).build();
const checkbox = () =>
  SpreadsheetApp.newDataValidation().requireCheckbox().setAllowInvalid(true).build();
const none = () => null;

// -----------------------------------------------------------------------------
// Table Schemas: (column order = required header order)
// -----------------------------------------------------------------------------

const PLAIN_BILL_SCHEMA = [
  { name: 'Item', rule: uniqueNonBlank },
  { name: 'Pay Category', rule: dropdown(PAY_CATEGORIES) },
  { name: 'Period Cost', rule: numberMin(0) },
  { name: 'Period Size', rule: numberMin(0) },
  { name: 'Period Type', rule: dropdown(PERIOD_TYPES) },
  { name: 'Start Date', rule: date },
  { name: 'Close Date', rule: date },
  { name: 'CPI Category', rule: dropdown(CPI_CATEGORIES) },
  { name: 'Sales Taxed', rule: checkbox },
  { name: 'Notes', rule: none },
];

const USAGE_BILL_SCHEMA = [
  { name: 'Item', rule: uniqueNonBlank },
  { name: 'Pay Category', rule: dropdown(PAY_CATEGORIES) },
  { name: 'Unit Cost', rule: numberMin(0) },
  { name: 'Unit Cost Base', rule: numberMin(0) },
  { name: 'Unit', rule: nonBlank },
  { name: 'Usage Rate', rule: numberMin(0) },
  { name: 'Period Size', rule: numberMin(0) },
  { name: 'Period Type', rule: dropdown(PERIOD_TYPES) },
  { name: 'Start Date', rule: date },
  { name: 'Close Date', rule: date },
  { name: 'CPI Category', rule: dropdown(CPI_CATEGORIES) },
  { name: 'Sales Taxed', rule: checkbox },
  { name: 'Item Notes', rule: none },
  { name: 'Usage Notes', rule: none },
];

const SUPPLY_COST_SCHEMA = [
  { name: 'Item', rule: uniqueNonBlank },
  { name: 'Pay Category', rule: dropdown(PAY_CATEGORIES) },
  { name: 'Unit Cost', rule: numberMin(0) },
  { name: 'Supply', rule: numberMin(0) },
  { name: 'Demand', rule: numberMin(0) },
  { name: 'Sales Taxed', rule: checkbox },
  { name: 'Notes', rule: none },
];

const LVE_SCHEMA_BY_CATEGORY = {
  services: PLAIN_BILL_SCHEMA,
  obligations: PLAIN_BILL_SCHEMA,
  nondurables: USAGE_BILL_SCHEMA,
  durables: SUPPLY_COST_SCHEMA,
};

// -----------------------------------------------------------------------------
// Core Validation
// -----------------------------------------------------------------------------

function validateSheet(name, schema) {
  const sheet = SSHEET.getSheetByName(name);
  if (!sheet) throw new Error(`"${name}": sheet is missing`);

  const columnNames = schema.map((header) => header.name);
  const columnCount = sheet.getLastColumn();
  if (columnNames.length !== columnCount) throw new Error(`"${name}": Columns missing.`);

  const headRowVals = sheet.getRange(1, 1, 1, columnCount).getValues()[0].map(String);
  const missingCols = columnNames.filter((h) => !headRowVals.includes(h));
  if (missingCols.length) throw new Error(`${name}: Incorrect number of columns.`);

  const columnPosByName = new Map(headRowVals.map((h, i) => [h, i + 1]));
  const totalRows = sheet.getLastRow() - 1;
  if (totalRows <= 0) return;

  // Keeps script reruns idempotent.
  sheet.getRange(2, 1, totalRows, columnCount).clearDataValidations();

  schema.forEach(({ name, rule }) => {
    const colPos = columnPosByName.get(name);
    const colRule = rule(colPos);
    if (colRule) sheet.getRange(2, colPos, totalRows).setDataValidation(colRule);
  });
}

// -----------------------------------------------------------------------------
// Entry Points
// -----------------------------------------------------------------------------

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Validation')
    .addItem('Run Validation', 'runValidation')
    .addToUi();
  runValidation();
}

function runValidation() {
  const errors = [];

  for (const [sheetName, schema] of Object.entries(LVE_SCHEMA_BY_CATEGORY)) {
    try {
      validateSheet(sheetName, schema);
    } catch (err) {
      errors.push(err.message || String(err));
    }
  }

  if (errors.length) SpreadsheetApp.getUi().alert(errors.join('\n'));
}
