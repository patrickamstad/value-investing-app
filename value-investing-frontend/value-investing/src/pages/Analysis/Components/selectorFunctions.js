// import { type } from "@testing-library/user-event/dist/type";
import {
  computeTotalLiabilities,
  sumBalanceSheetItems,
} from "../../valuation/components/selectorFunctions";

export function computeOpIncomeTopDown(data, caseIndex) {
  var opIncome = data?.revenue[caseIndex] * data?.op_margins[caseIndex];

  return opIncome;
}

export function computeOpIncomeBottomUp(data, caseIndex) {
  var opIncome =
    data?.revenue[caseIndex] -
    data?.cogs[caseIndex] -
    data?.sga[caseIndex] -
    data?.rnd[caseIndex] -
    data?.other_opex[caseIndex];

  return opIncome;
}

export function computeOpMarginBottomUp(data, caseIndex) {
  var opIncome = computeOpIncomeBottomUp(data, caseIndex);
  return opIncome / data?.revenue[caseIndex];
}

export function computeNopatTopDown(data, taxRate, caseIndex) {
  var nopat =
    data?.revenue[caseIndex] * data?.op_margins[caseIndex] * (1 - taxRate);

  return nopat;
}

export function computeNopatBottomUp(data, taxRate, caseIndex) {
  var opIncome = computeOpIncomeBottomUp(data, caseIndex);
  return opIncome * (1 - taxRate);
}

export function computeEquityVal(b0, nopat, wacc, noa, g, caseIndex) {
  if (!b0 || !noa) return null;

  //compute residual earnings 1 = (NOPAT - r*NOA)/(1+r)
  var re1 = (nopat[caseIndex] - wacc * noa[caseIndex]) / (1 + wacc);

  // compute second term = (NOPAT - r*NOA)/((1+r)*(r-g))
  var re2 =
    (nopat[caseIndex] - wacc * noa[caseIndex]) / ((1 + wacc) * (wacc - g));

  return b0[caseIndex] + re1 + re2;
}

export function computeNetOpAssets(data, caseIndex) {
  if (!data?.operatingAssets || !data?.operatingLiabilities) return null;
  return data.operatingAssets[caseIndex] - data.operatingLiabilities[caseIndex];
}

export function computeTotAssets(balanceSheet) {
  const sumCurrentAssets = sumBalanceSheetItems(balanceSheet.currentAssets);
  const sumNonCurrentAssets = sumBalanceSheetItems(
    balanceSheet.nonCurrentAssets
  );

  return sumCurrentAssets + sumNonCurrentAssets;
}

export function computeTotLiab(balanceSheet) {
  const sumCurrentLiab = sumBalanceSheetItems(balanceSheet.currentLiab);
  const sumNonCurrentLiab = sumBalanceSheetItems(balanceSheet.nonCurrentLiab);

  return sumCurrentLiab + sumNonCurrentLiab;
}

export function computeNetLiqValue(balanceSheet) {
  const totalAssets = computeTotAssets(balanceSheet);
  const totalLiabilities = computeTotLiab(balanceSheet);

  return totalAssets - totalLiabilities;
}

export function computeRnoa(nopat, noa, taxRate) {
  return (nopat * (1 - taxRate)) / noa;
}

export function computeAto(data, caseIndex) {
  if (!data?.revenue || !data?.netOperatingAssets) return null;
  return data.revenue[caseIndex] / data.netOperatingAssets[caseIndex];
}
