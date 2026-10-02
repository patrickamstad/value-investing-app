import { createSlice } from "@reduxjs/toolkit";
import { ExistingModel, type SelectedModel } from "./analysisTypes";
import { PayloadAction } from "@reduxjs/toolkit";

const initialState = {
  selectedTickerSymbol: null,
  companyData: {},
  valuationData: {
    revenue: [0, 0, 0],
    cogs: [0, 0, 0],
    sga: [0, 0, 0],
    rnd: [0, 0, 0],
    other_opex: [0, 0, 0],
    op_margins: [0, 0, 0],
  },
  balanceSheet: {},
  valuationApproach: "topDown",
  taxRate: 0.25,
  wacc: 0.1,
  terminalGrowthRate: 0,
  // session-only override for this company's reporting currency (see get_fx_rate on
  // the backend) - null means "use whatever the backend auto-detects". Never written
  // to the DB; just re-triggers a recompute with the user-supplied currency instead.
  reportingCurrencyOverride: null as string | null,
  // same idea, for TradedCompanies.currency (the currency last_close_price is quoted
  // in). Far more rarely wrong than reporting currency, so the UI gates editing this
  // one behind an extra "unlock" step - but the override mechanism itself is identical.
  tradingCurrencyOverride: null as string | null,
  // purely a display choice for the fundamentals table (ValuationModel's historical
  // year/TTM columns) - "trading" (default) shows the same currency as the valuation
  // summary cards; "reporting" divides back down to the currency as originally filed,
  // for cross-checking against the actual report. Computed client-side from the
  // already-fetched fxRate; never triggers a re-fetch and never affects the bear/base/
  // bull valuation numbers, which always stay in trading currency.
  tableCurrencyMode: "trading" as "trading" | "reporting",
  // same idea, independently, for the Net Liq. Value balance-sheet breakdown
  // (AssetTable/LiabilitiesTable). Kept separate from tableCurrencyMode since these
  // are different sections of the page. While set to "reporting", editing the
  // per-line-item value/multiplier is disabled - those inputs write straight into
  // the canonical trading-currency store, so editing under a divided-down display
  // would require converting back on every keystroke; simpler and safer to require
  // switching back to trading currency to edit (view-only while comparing).
  liquidationTableCurrencyMode: "trading" as "trading" | "reporting",
  savedModels: [] as ExistingModel[],
  selectedModel: { isNew: true } as SelectedModel,
};

export const analysisSlice = createSlice({
  name: "analysis",
  initialState,
  reducers: {
    initializeTickerSymbol: (state, action) => {
      state.selectedTickerSymbol = action.payload;
      // a currency override applied to the previous company shouldn't carry over
      state.reportingCurrencyOverride = null;
      state.tradingCurrencyOverride = null;
    },
    setReportingCurrencyOverride: (state, action) => {
      state.reportingCurrencyOverride = action.payload;
    },
    setTradingCurrencyOverride: (state, action) => {
      state.tradingCurrencyOverride = action.payload;
    },
    setTableCurrencyMode: (state, action) => {
      state.tableCurrencyMode = action.payload;
    },
    setLiquidationTableCurrencyMode: (state, action) => {
      state.liquidationTableCurrencyMode = action.payload;
    },
    initializeCompanyData: (state, action) => {
      state.companyData = action.payload;
    },
    initalizeBalanceSheet: (state, action) => {
      state.balanceSheet = action.payload;
    },
    setValuationApproach: (state, action) => {
      state.valuationApproach = action.payload;
    },
    initializeValuationData: (state, action) => {
      state.valuationData = action.payload;
    },
    updateValuationData: (state, action) => {
      const { newValue, metricName, caseIndex, scaleFactor } = action.payload;
      state.valuationData[metricName][caseIndex] = newValue * scaleFactor;
    },
    updateLiquidationValuationData: (state, action) => {
      const { category, metric, newValue } = action.payload;

      //extract correct category. Catgories are currentAssets, nonCurrentAssets, currentLiabilities, etc.
      const items = state.balanceSheet[category];
      if (!items) return; // Invalid category

      // find the metric of interest
      const target = items.find((entry) => entry.metric === metric);
      if (!target) return; // Metric not found

      target.value = newValue; // Immer lets you mutate directly
    },
    updateLiqValMultChange: (state, action) => {
      const { category, metric, newValue } = action.payload;

      const items = state.balanceSheet[category];
      if (!items) return; // Invalid category

      // find the metric of interest
      const target = items.find((entry) => entry.metric === metric);
      if (!target) return; // Metric not found

      target.multiplier = newValue; // Immer lets you mutate directly
    },
    changeTaxRate: (state, action) => {
      state.taxRate = action.payload;
    },
    changeWacc: (state, action) => {
      state.wacc = action.payload;
    },
    changeNrShares: (state, action) => {
      (state.companyData as any).nrShares = action.payload;
    },
    changeTerminalGrowthRate: (state, action) => {
      state.terminalGrowthRate = Number(action.payload);
    },
    initializeSavedModels: (state, action: PayloadAction<ExistingModel[]>) => {
      state.savedModels = action.payload;
    },
    setSelectedModel: (state, action: PayloadAction<SelectedModel>) => {
      state.selectedModel = action.payload;
    },
    updateSavedModels: (state, action: PayloadAction<ExistingModel>) => {
      //check if model already exists
      const modelIndex = state.savedModels.findIndex(
        (item) => item.id === action.payload.id
      );

      if (modelIndex === -1) {
        state.savedModels.push(action.payload);
      } else {
        state.savedModels[modelIndex] = action.payload;
      }
    },
  },
});

export const {
  changeTaxRate,
  updateLiquidationValuationData,
  updateLiqValMultChange,
  changeNrShares,
  changeWacc,
  changeTerminalGrowthRate,
  setReportingCurrencyOverride,
  setTradingCurrencyOverride,
  setTableCurrencyMode,
  setLiquidationTableCurrencyMode,
  initializeValuationData,
  initializeTickerSymbol,
  initializeCompanyData,
  setValuationApproach,
  updateValuationData,
  initalizeBalanceSheet,
  initializeSavedModels,
  setSelectedModel,
  updateSavedModels,
} = analysisSlice.actions;

export default analysisSlice.reducer;
