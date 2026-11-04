type G1450CardValidationPayload = {
  cardholder_name: string;
  credit_card_number: string;
  expiration_month: string;
  expiration_year: string;
  security_code: string;
  billing_address: {
    street_1: string;
    city: string;
    state: string;
    postal_code: string;
  };
};

function fieldIssue(label: string, value: string, minimumLength: number, unit = "characters") {
  const trimmed = value.trim();
  if (!trimmed) {
    return label;
  }
  if (trimmed.length < minimumLength) {
    return `${label} (${minimumLength}+ ${unit})`;
  }
  return null;
}

export function getG1450PaymentFieldIssues(form: G1450CardValidationPayload) {
  const cardDigits = form.credit_card_number.replace(/\D/g, "");
  return [
    fieldIssue("cardholder name", form.cardholder_name, 1),
    !cardDigits ? "card number" : cardDigits.length < 12 ? "card number (12+ digits)" : null,
    fieldIssue("expiration month", form.expiration_month, 1),
    fieldIssue("expiration year", form.expiration_year, 2),
    fieldIssue("CVV", form.security_code, 3),
    fieldIssue("billing street address", form.billing_address.street_1, 1),
    fieldIssue("billing city", form.billing_address.city, 1),
    fieldIssue("billing state", form.billing_address.state, 2),
    fieldIssue("billing ZIP code", form.billing_address.postal_code, 3),
  ].filter((value): value is string => Boolean(value));
}

export function getG1650PaymentFieldIssues(form: {
  account_ownership: string;
  account_holder_name: string;
  business_name: string;
  bank_name: string;
  routing_number: string;
  account_number: string;
}) {
  const routingDigits = form.routing_number.replace(/\D/g, "");
  const accountDigits = form.account_number.replace(/\D/g, "");
  return [
    form.account_ownership === "business"
      ? fieldIssue("business name", form.business_name, 1)
      : fieldIssue("account holder name", form.account_holder_name, 1),
    fieldIssue("bank name", form.bank_name, 1),
    routingDigits.length !== 9 ? "routing number (9 digits)" : null,
    accountDigits.length < 4 ? "account number (4+ digits)" : null,
  ].filter((value): value is string => Boolean(value));
}

export function formatFieldList(values: string[]) {
  if (values.length <= 1) {
    return values.join("");
  }
  if (values.length === 2) {
    return `${values[0]} and ${values[1]}`;
  }
  return `${values.slice(0, -1).join(", ")}, and ${values[values.length - 1]}`;
}
