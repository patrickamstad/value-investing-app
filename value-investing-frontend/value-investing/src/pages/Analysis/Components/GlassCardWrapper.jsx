import React from "react";
import { TextField, MenuItem } from "@mui/material";
import { getCurrencySymbol } from "../../valuation/components/selectorFunctions";
import ValuationModelDefinition from "./ValuationModelDefinition";
import ValuationApproachSelect from "./ValuationApproachSelect";

function GlassCardWrapper({
  children,
  title,
  currencyCode,
  lastClosePrice,
  qfsSymbol,
  tableCurrencyMode,
  onTableCurrencyModeChange,
  tradingCurrencyCode,
  reportingCurrencyCode,
}) {
  return (
    <div className="glass-card" style={{ marginTop: "12px" }}>
      <div
        className="title-mid-size"
        style={{
          marginBottom: "20px",
          display: "flex",
          gap: "12px",
          justifyContent: "space-between",
        }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {title} {qfsSymbol}
          <ValuationModelDefinition />
          {
            <span
              className="title-last-close-price"
              style={{ fontSize: "14px" }}>
              (Last Close Price: {getCurrencySymbol(currencyCode)}{" "}
              {lastClosePrice})
            </span>
          }
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {onTableCurrencyModeChange && (
            <TextField
              select
              size="small"
              value={tableCurrencyMode}
              label="Table Currency"
              style={{ minWidth: "180px" }}
              onChange={(e) => onTableCurrencyModeChange(e.target.value)}>
              <MenuItem value="trading">
                {tradingCurrencyCode
                  ? `Trading Currency (${tradingCurrencyCode})`
                  : "Trading Currency"}
              </MenuItem>
              <MenuItem value="reporting" disabled={!reportingCurrencyCode}>
                {reportingCurrencyCode
                  ? `Reporting Currency (${reportingCurrencyCode})`
                  : "Reporting Currency"}
              </MenuItem>
            </TextField>
          )}
          <ValuationApproachSelect />
        </div>
      </div>
      {children}
    </div>
  );
}

export default GlassCardWrapper;
