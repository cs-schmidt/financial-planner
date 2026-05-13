/**
 * A Google Apps Script which provides functions to validate the structure and content of
 * an expense spreadsheet
 *
 * Requirements:
 *   - This script must be treated as a container-bound script under your target Google
 *     Sheets file.
 *   - The Google Sheets file should have its time zone set to your local time zone.
 */

const SSHEET = SpreadsheetApp.getActiveSpreadsheet();
const EXPENSE_HEADERS_BY_NAME = {
  services: [
    'Item',
    'Category',
    'Period Cost',
    'Period Type',
    'Period Size',
    'Start Date',
    'Add Sales Tax',
    'CPI Category',
    'Notes',
  ],
  nondurables: [
    'Item',
    'Category',
    'Unit Cost',
    'Unit Cost Base',
    'Unit',
    'Usage Rate',
    'Period Type',
    'Period Size',
    'Start Date',
    'Add Sales Tax',
    'CPI Category',
    'Item Notes',
    'Usage Notes',
  ],
  obligations: [
    'Item',
    'Category',
    'Period Cost',
    'Period Type',
    'Period Size',
    'Periods',
    'Start Date',
    'CPI Category',
    'Notes',
  ],
  durables: [
    'Item',
    'Category',
    'Unit Cost',
    'Supply',
    'Demand',
    'Add Sales Tax',
    'Cover',
    'Notes',
  ],
};
const EXPENSE_SHEET_NAMES = Object.keys(EXPENSE_HEADERS_BY_NAME);
const EXPENSE_CATEGORIES = [
  'Housing',
  'Auto',
  'Food & Dining',
  'Health & Personal Care',
  'Clothing',
  'Education & Research',
  'Furnishings & Textiles',
  'Kitchen Equipment & Supplies',
  'Electronics & Software',
  'Cleaning',
  'Other Operations & Equipment',
  'Transport & Travel',
  'Finance & Legal',
  'Recreation',
  'Other Expenses',
];
const CPI_CATEGORIES = [
  'Food purchased from stores',
  'Food purchased from restaurants',
  'Rent',
  "Tenants' insurance premiums",
  'Electricity',
  'Water',
  'Natural gas',
  'Fuel oil and other fuels',
  'Telephone services',
  'Postal and other communications services',
  'Internet access services',
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
  'Upholstered furniture',
  'Wooden furniture',
  'Other furniture',
  'Bedding and other household textiles',
  'Cooking appliances',
  'Refrigerators and freezers',
  'Laundry and dishwashing appliances',
  'Other household appliances',
  'Non-electric kitchen utensils, tableware and cookware',
  'Household tools (including lawn, garden and snow removal equipment)',
  'Other household equipment',
  "Men's clothing",
  "Men's footwear (excluding athletic)",
  'Athletic footwear',
  'Clothing accessories',
  'Watches',
  'Clothing material, notions and services',
  'Gasoline',
  'Passenger vehicle parts, accessories and supplies',
  'Passenger vehicle maintenance and repair services',
  'Passenger vehicle insurance premiums',
  'Passenger vehicle registration fees',
  "Drivers' licences",
  'Parking fees',
  'City bus and subway transportation',
  'Air transportation',
  'Prescribed medicines (excluding medicinal cannabis)',
  'Non-prescribed medicines',
  'Eye care goods',
  'Other health care goods',
  'Eye care services',
  'Dental care services',
  'Other health care services',
  'Personal soap',
  'Toiletry items and cosmetics',
  'Oral-hygiene products',
  'Other personal care supplies and equipment',
  'Personal care services',
  'Computer equipment, software and supplies',
  'Multipurpose digital devices',
  'Recreational services',
  'School textbooks and supplies',
  'Other lessons, courses and education services',
  'Books and reading material (excluding textbooks)',
  'Alcoholic beverages purchased from stores',
];
const PERIOD_TYPES = ['Year', 'Month', 'Week', 'Day'];

// NOTE: The `onOpen()` handler acts as this scripts "main function".
/**
 * The event handler triggered when opening the spreadsheet.
 * @param {Event} evt - The onOpen event object.
 * @returns {void}
 */
function onOpen(evt) {
  try {
    addServiceExpenseValidations(SSHEET);
    addNondurableExpenseValidations(SSHEET);
    addObligationExpenseValidations(SSHEET);
    addDurableExpenseValidation(SSHEET);
  } catch (err) {
    let message;
    if (err instanceof Error) message = err.message || 'Something went wrong.';
    else message = 'Something went wrong';
    SpreadsheetApp.getUi().alert(message);
  }
}

// =============================================================================
// Sheet Validation
// =============================================================================

/**
 * Adds data validations to columns in the "services" expense sheet. An error is thrown if
 * the sheet, or its required columns or headers are omitted.
 * @param {Spreadsheet} ssheet - A Spreadsheet instance containing a "services" sheet.
 * @returns {void}
 */
function addServiceExpenseValidations(ssheet) {
  const sheet = ssheet.getSheetByName('services');
  if (!sheet) throw Error(`Cannot add service validations: missing "services" sheet.`);
  const totalColumns = sheet.getLastColumn();
  const totalColumnsNeeded = EXPENSE_HEADERS_BY_NAME['services'].length;
  if (totalColumnsNeeded != totalColumns) {
    const message =
      `Cannot add service validations:` +
      `expected ${totalColumnsNeeded} columns, found ${totalColumns}.`;
    throw Error(message);
  }
  const headers = new Set(getSheetHeaders(sheet));
  const missingHeaders = EXPENSE_HEADERS_BY_NAME['services'].filter(
    (header) => !headers.has(header)
  );
  if (missingHeaders.length)
    throw Error(`Cannot add service validations: missing headers ${missingHeaders}.`);
  const columnIndexByHeader = new Map([...headers].map((header, i) => [header, i + 1]));
  addUniquenessValidation(sheet, columnIndexByHeader.get('Item'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Category'), EXPENSE_CATEGORIES);
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Period Cost'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Period Type'), PERIOD_TYPES);
  addMinIntValidation(sheet, columnIndexByHeader.get('Period Size'), 1);
  addStartDateValidation(sheet, columnIndexByHeader.get('Start Date'));
  addCheckboxValidation(sheet, columnIndexByHeader.get('Add Sales Tax'));
  addDropdownValidation(sheet, columnIndexByHeader.get('CPI Category'), CPI_CATEGORIES);
}

/**
 * Adds data validations to columns in the "nondurables" expense sheet. An error is thrown
 * if the sheet, or its required columns or headers are omitted.
 * @param {Spreadsheet} ssheet - A Spreadsheet instance containing a "nondurables" sheet.
 * @returns {void}
 */
function addNondurableExpenseValidations(ssheet) {
  const sheet = ssheet.getSheetByName('nondurables');
  if (!sheet)
    throw Error(`Cannot add nondurable validations: missing "nondurables" sheet.`);
  const totalColumns = sheet.getLastColumn();
  const totalColumnsNeeded = EXPENSE_HEADERS_BY_NAME['nondurables'].length;
  if (totalColumns !== totalColumnsNeeded) {
    const message =
      `Cannot add nondurable validations:` +
      `expected ${totalColumnsNeeded} columns, found ${totalColumns}.`;
    throw Error(message);
  }
  const headers = new Set(getSheetHeaders(sheet));
  const missingHeaders = EXPENSE_HEADERS_BY_NAME['nondurables'].filter(
    (header) => !headers.has(header)
  );
  if (missingHeaders.length)
    throw Error(`Cannot add nondurable validations: missing headers ${missingHeaders}.`);
  const columnIndexByHeader = new Map([...headers].map((header, i) => [header, i + 1]));
  addUniquenessValidation(sheet, columnIndexByHeader.get('Item'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Category'), EXPENSE_CATEGORIES);
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Unit Cost'));
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Unit Cost Base'));
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Usage Rate'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Period Type'), PERIOD_TYPES);
  addMinIntValidation(sheet, columnIndexByHeader.get('Period Size'), 1);
  addStartDateValidation(sheet, columnIndexByHeader.get('Start Date'));
  addCheckboxValidation(sheet, columnIndexByHeader.get('Add Sales Tax'));
  addDropdownValidation(sheet, columnIndexByHeader.get('CPI Category'), CPI_CATEGORIES);
}

/**
 * Adds data validations to columns in the "obligations" expense sheet. An error is thrown
 * if the sheet, or its required columns or headers are omitted.
 * @param {Spreadsheet} ssheet - A Spreadsheet instance containing an "obligations" sheet.
 * @returns {void}
 */
function addObligationExpenseValidations(ssheet) {
  const sheet = ssheet.getSheetByName('obligations');
  if (!sheet)
    throw Error(`Cannot add obligation validations: missing "obligations" sheet.`);
  const totalColumns = sheet.getLastColumn();
  const totalColumnsNeeded = EXPENSE_HEADERS_BY_NAME['obligations'].length;
  if (totalColumns !== totalColumnsNeeded) {
    const message =
      `Cannot add obligation validations:` +
      `expected ${totalColumnsNeeded} columns, found ${totalColumns}.`;
    throw Error(message);
  }
  const headers = new Set(getSheetHeaders(sheet));
  const missingHeaders = EXPENSE_HEADERS_BY_NAME['obligations'].filter(
    (header) => !headers.has(header)
  );
  if (missingHeaders.length)
    throw Error(`Cannot add obligation validations: missing headers ${missingHeaders}.`);
  const columnIndexByHeader = new Map([...headers].map((header, i) => [header, i + 1]));
  addUniquenessValidation(sheet, columnIndexByHeader.get('Item'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Category'), EXPENSE_CATEGORIES);
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Period Cost'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Period Type'), PERIOD_TYPES);
  addMinIntValidation(sheet, columnIndexByHeader.get('Period Size'), 1);
  addMinIntValidation(sheet, columnIndexByHeader.get('Periods'), 1);
  addStartDateValidation(sheet, columnIndexByHeader.get('Start Date'));
  addDropdownValidation(sheet, columnIndexByHeader.get('CPI Category'), CPI_CATEGORIES);
}

/**
 * Adds data validations to columns in the "durables" expense sheet. An error is thrown if
 * the sheet, or its required columns or headers are omitted.
 * @param {Spreadsheet} ssheet - A Spreadsheet instance containing a "durables" sheet.
 * @returns {void}
 */
function addDurableExpenseValidation(ssheet) {
  const sheet = ssheet.getSheetByName('durables');
  if (!sheet) throw Error(`Cannot add durable validations: missing "durables" sheet.`);
  const totalColumns = sheet.getLastColumn();
  const totalColumnsNeeded = EXPENSE_HEADERS_BY_NAME['durables'].length;
  if (totalColumns !== totalColumnsNeeded) {
    const message =
      `Cannot add durable validations:` +
      `expected ${totalColumnsNeeded} columns, found ${totalColumns}.`;
    throw Error(message);
  }
  const headers = new Set(getSheetHeaders(sheet));
  const missingHeaders = EXPENSE_HEADERS_BY_NAME['durables'].filter(
    (header) => !headers.has(header)
  );
  if (missingHeaders.length)
    throw Error(`Cannot add durable validations: missing headers ${missingHeaders}.`);
  const columnIndexByHeader = new Map([...headers].map((header, i) => [header, i + 1]));
  addUniquenessValidation(sheet, columnIndexByHeader.get('Item'));
  addDropdownValidation(sheet, columnIndexByHeader.get('Category'), EXPENSE_CATEGORIES);
  addPositiveFloatValidation(sheet, columnIndexByHeader.get('Unit Cost'));
  addMinIntValidation(sheet, columnIndexByHeader.get('Supply'));
  addMinIntValidation(sheet, columnIndexByHeader.get('Demand'), 1);
  addCheckboxValidation(sheet, columnIndexByHeader.get('Add Sales Tax'));
  // Add validation for Cover column.
  const obligSheet = SSHEET.getSheetByName('obligations');
  if (!obligSheet)
    throw Error('Cannot add "Cover" validation: missing "obligations" sheet.');
  const obligHeaders = getSheetHeaders(obligSheet);
  const obligItemIndex = obligHeaders.indexOf('Item') + 1;
  const obligItemAlphaCode = getColumnAlphabetCode(obligItemIndex);
  const coverIndex = Array.from(headers).indexOf('Cover') + 1;
  const coverAlphaCode = getColumnAlphabetCode(columnIndexByHeader.get('Cover'));
  const coverDataRange = sheet.getRange(2, coverIndex, sheet.getLastRow() - 1);
  const coverFormula = `=COUNTIF(${[
    `obligations!${obligItemAlphaCode}2:${obligItemAlphaCode}`,
    `${coverAlphaCode}2`,
  ].join()})`;
  const coverRule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(coverFormula)
    .setAllowInvalid(true)
    .build();
  coverDataRange.setDataValidation(coverRule);
}

// =============================================================================
// Data Validation
// =============================================================================

/**
 * Adds uniqueness validation to the sheet, under the column index.
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 */
function addUniquenessValidation(sheet, columnIndex) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const alphaCode = getColumnAlphabetCode(columnIndex);
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(`=COUNTIF(${alphaCode}2:${alphaCode}, ${alphaCode}2) = 1`)
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

/**
 * Adds dropdown validation to the sheet, under the given column index, where the
 * acceptable values are in list.
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 * @param {string[]} list - The list of values which are options for the dropdown.
 */
function addDropdownValidation(sheet, columnIndex, list) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  if (!(list instanceof Array)) throw TypeError(`Parameter 'list' must be an Array.`);
  if (!list.every((value) => typeof value == 'string'))
    throw TypeError(`Parameter 'list' can only contain strings.`);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(list, true)
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

/**
 * Adds positive floating-point number validation to the sheet, under the given column
 * index.
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 */
function addPositiveFloatValidation(sheet, columnIndex) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const alphaCode = getColumnAlphabetCode(columnIndex);
  const codeRange = `${alphaCode}2:${alphaCode}`;
  const formula = `=AND(ISNUMBER(${codeRange}), ${codeRange}>0)`;
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

/**
 * Adds minimum integer validation to the sheet, under the given column index. Validation
 * enforces values being greater than or equal to `min` (which is 0 by default).
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 * @param {number} min - A number greater than or equal to 0.
 */
function addMinIntValidation(sheet, columnIndex, min = 0) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  if (typeof min != 'number') throw TypeError(`Parameter 'min' must be a number.`);
  if (!Number.isInteger(min) || min < 0)
    throw Error(`Parameter 'min' is an invalid number.`);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const alphaCode = getColumnAlphabetCode(columnIndex);
  const codeRange = `${alphaCode}2:${alphaCode}`;
  const formula = `=AND(${[
    `ISNUMBER(${codeRange})`,
    `INT(${codeRange})=${codeRange}`,
    `${codeRange}>=${min}`,
  ].join()})`;
  const rule = SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

/**
 * Adds start date validation to the sheet, under the given column index.
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 */
function addStartDateValidation(sheet, columnIndex) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const rule = SpreadsheetApp.newDataValidation()
    .requireDate()
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

/**
 * Adds checkbox validation to the sheet, under the given column index.
 * @param {Sheet} sheet - The sheet instance where the validation is added.
 * @param {number} columnIndex - The index of the column within the sheet.
 */
function addCheckboxValidation(sheet, columnIndex) {
  assertIsSheet(sheet);
  assertPositiveInteger(columnIndex);
  const totalRows = sheet.getLastRow() - 1;
  const dataRange = sheet.getRange(2, columnIndex, totalRows);
  const rule = SpreadsheetApp.newDataValidation()
    .requireCheckbox()
    .setAllowInvalid(true)
    .build();
  dataRange.setDataValidation(rule);
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Gets the header row within the sheet as an array.
 * @param {Sheet} sheet - A sheet within a spreadsheet.
 * @returns {any[]}
 */
function getSheetHeaders(sheet) {
  assertIsSheet(sheet);
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
}

/**
 * Produces the alphabetical code corresponding to the column index.
 * @param {number} columnIndex - The column index (a positive integer).
 * @returns {string}
 */
function getColumnAlphabetCode(columnIndex) {
  assertPositiveInteger(columnIndex);
  let alphabetCode = '';
  while (columnIndex > 0) {
    const letterCode = 65 + ((columnIndex - 1) % 26);
    alphabetCode = String.fromCharCode(letterCode) + alphabetCode;
    columnIndex = Math.floor((columnIndex - 1) / 26);
  }
  return alphabetCode;
}

/**
 * Asserts that the value provided is a Sheet object.
 * @param {any} value - The value to validate as a Sheet object.
 * @throws {TypeError} If the value is not a Sheet object.
 * @returns {void}
 */
function assertIsSheet(value) {
  if (!(value && typeof value.getName == 'function'))
    throw TypeError(`Expected 'sheet' to be a Sheet object.`);
}

/**
 * Asserts that the value provided is a positive integer.
 * @param {any} value - The value to validate as a positive integer.
 * @throws {TypeError} If the value passed is not a number value.
 * @throws {Error} If the number passed is not a positive integer.
 * @returns {void}
 */
function assertPositiveInteger(value) {
  if (!(typeof value == 'number'))
    throw TypeError(`Expected 'columnIndex' to be a Number (value or instance).`);
  if (!(Number.isInteger(value) || value > 0))
    throw Error(`Expected 'columnIndex' to be a positive integer, got ${value}`);
}
