import React from "react";
import { TextField, MenuItem } from "@mui/material";
import ToggleButtonsScaling from "./ToggleButtonsScaling";
import AssetTable from "./AssetTable";
import LiabilitiesTable from "./LiabilitiesTable";
import ValuationSummaryCard from "./ValuationSummaryCard";
import { useDispatch, useSelector } from "react-redux";
import { computeNetLiqValue } from "./selectorFunctions";
import { getCurrencySymbol } from "../../valuation/components/selectorFunctions";
import { setLiquidationTableCurrencyMode } from "../../../features/analysisSlice";

const tableColumnWidths = ["40%", "10%", "10%", "15%"];

function LiquidationValue({
  qfsSymbol,
  scaling,
  handleToggleButtonChange,
  currencyCode,
  nrShares,
  lastClosePrice,
}) {
  const dispatch = useDispatch();
  // Net Liq. Value always stays in trading currency, computed straight from the
  // canonical (un-rescaled) store - the table currency toggle below only changes how
  // AssetTable/LiabilitiesTable *display* their line items, never this summary.
  const netLiqValue = useSelector((state) =>
    computeNetLiqValue(state.analysis?.balanceSheet)
  );

  const valPerShare = netLiqValue / nrShares;

  const tableCurrencyMode = useSelector(
    (state) => state.analysis?.liquidationTableCurrencyMode
  );
  const fxRate = useSelector((state) => state.analysis?.companyData?.fxRate);
  const reportingCurrencyCode = useSelector(
    (state) => state.analysis?.companyData?.reportingCurrency
  );
  const isReportingView = tableCurrencyMode === "reporting";
  // divides the (always trading-currency) stored values back down for display only;
  // editing is disabled whenever this isn't 1 (see AssetValLineItem) rather than
  // trying to convert typed input back on every keystroke.
  const displayDivisor = isReportingView && fxRate ? fxRate : 1;

  return (
    <div style={{ marginTop: "32px" }}>
      {" "}
      <div className="button-group-wrapper">
        <ToggleButtonsScaling
          value={scaling}
          handleChange={handleToggleButtonChange}
        />
      </div>
      <div className="glass-card" style={{ marginTop: "12px" }}>
        <div
          className="title-mid-size"
          style={{
            marginBottom: "20px",
            display: "flex",
            gap: "12px",
            justifyContent: "space-between",
          }}>
          <div>
            Liquidation Valuation Analysis {qfsSymbol}{" "}
            <span
              className="title-last-close-price"
              style={{ fontSize: "14px", marginLeft: "10px" }}>
              (Last Close Price: {getCurrencySymbol(currencyCode)}{" "}
              {lastClosePrice})
            </span>
          </div>
          <TextField
            select
            size="small"
            value={tableCurrencyMode}
            label="Table Currency"
            style={{ minWidth: "180px" }}
            onChange={(e) =>
              dispatch(setLiquidationTableCurrencyMode(e.target.value))
            }>
            <MenuItem value="trading">
              {currencyCode ? `Trading Currency (${currencyCode})` : "Trading Currency"}
            </MenuItem>
            <MenuItem value="reporting" disabled={!reportingCurrencyCode}>
              {reportingCurrencyCode
                ? `Reporting Currency (${reportingCurrencyCode})`
                : "Reporting Currency"}
            </MenuItem>
          </TextField>
        </div>
        <div
          className="flex-wrapper-valuation-summary"
          style={{ marginBottom: "20px" }}>
          <ValuationSummaryCard
            currencyCode={currencyCode}
            title="Net Liq. Value (per share)"
            price={valPerShare.toFixed(2)}
            colorPrice={
              valPerShare > lastClosePrice ? "undervalued" : "overvalued"
            }
            marginOfSafety={(
              ((valPerShare - lastClosePrice) / lastClosePrice) *
              100
            ).toFixed(1)}
          />
        </div>
        {isReportingView && (
          <div
            style={{
              fontSize: "0.75rem",
              opacity: 0.7,
              marginBottom: "12px",
            }}>
            Viewing in reporting currency for comparison - editing is disabled;
            switch back to Trading Currency to make changes.
          </div>
        )}

        <div className="liquidation-value-flex-wrapper">
          <AssetTable
            tableColumnWidths={tableColumnWidths}
            scaling={scaling}
            displayDivisor={displayDivisor}
            disabled={isReportingView}
          />
          <LiabilitiesTable
            tableColumnWidths={tableColumnWidths}
            scaling={scaling}
            displayDivisor={displayDivisor}
            disabled={isReportingView}
          />
        </div>
      </div>
    </div>
  );
}

export default LiquidationValue;
