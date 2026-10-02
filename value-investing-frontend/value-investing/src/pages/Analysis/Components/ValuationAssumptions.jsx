import React, { useState } from "react";
import { TextField, InputLabel, FormControl, InputAdornment } from "@mui/material";
import { useDispatch, useSelector } from "react-redux";
import {
  changeNrShares,
  changeTaxRate,
  changeTerminalGrowthRate,
  changeWacc,
  setReportingCurrencyOverride,
  setTradingCurrencyOverride,
} from "../../../features/analysisSlice";
import { NumericFormat } from "react-number-format";
import Tooltip from "@mui/material/Tooltip";
import useAxiosWithAuth from "../../../axios/useAxiosWithAuth";
import { useSnackbar } from "../../GlobalComponents/SnackbarProvider";
import CurrencyCorrectionField from "./CurrencyCorrectionField";

const SCALE_PERC = 100;

function ValuationAssumptions({ scalingFactor }) {
  const analysisData = useSelector((state) => state.analysis);
  const dispatch = useDispatch();
  const axiosInstanceAuth = useAxiosWithAuth();
  const { showMessage } = useSnackbar();
  const [errorTax, setErrorTax] = useState(false);
  const [errorWacc, setErrorWacc] = useState(false);
  const [errorG, setErrorG] = useState(false);
  const [errorNrShares, setErrorNrShares] = useState(false);

  // detected_* are always the raw DB values regardless of any session override (see
  // get_detected_currencies on the backend) - needed so "detected -> overridden" and
  // Revert stay correct even across multiple overrides in the same session.
  const detectedReportingCurrency = analysisData?.companyData?.reportingCurrencyDetected;
  const detectedTradingCurrency = analysisData?.companyData?.currencyDetected;
  const effectiveReportingCurrency =
    analysisData.reportingCurrencyOverride || detectedReportingCurrency;
  const effectiveTradingCurrency =
    analysisData.tradingCurrencyOverride || detectedTradingCurrency;

  // Persisting is a separate, explicit action from the session override - a DB write
  // here changes what every user sees for this company, not just this session, so it
  // must never fire automatically just from picking a value in the dropdown.
  const saveCurrencyCorrection = (field, overrideAction) => (value) => {
    const qfsSymbol = analysisData?.selectedTickerSymbol?.qfs_symbol;
    if (!qfsSymbol || !value) return Promise.resolve();

    return axiosInstanceAuth
      .post("/screener/correct-currency/", { qfsSymbol, [field]: value })
      .then(() => {
        showMessage(
          `Saved: ${qfsSymbol}'s ${field === "reportingCurrency" ? "reporting" : "trading"} currency is now ${value} for everyone.`,
          "success"
        );
        // the DB now matches the override, so it's no longer needed - clearing it
        // re-fetches and confirms the backend auto-detects the same value
        dispatch(overrideAction(null));
      })
      .catch((error) => {
        showMessage(`Error saving currency correction: ${error}`, "error");
        console.error("ERROR: POST /screener/correct-currency/: ", error);
      });
  };

  return (
    <div className="glass-card" style={{ marginTop: "20px" }}>
      {" "}
      <div className="title-mid-size" style={{ marginBottom: "20px" }}>
        Valuation Assumptions
      </div>
      <div className="valuation-inputs-flex-wrapper">
        <Tooltip
          placement="right-start"
          arrow
          open={errorTax}
          title="Invalid number">
          <NumericFormat
            id="taxrate-input"
            value={analysisData.taxRate * SCALE_PERC}
            decimalScale={1} // 1 decimal place
            decimalSeparator="." // use dot for decimal
            customInput={TextField}
            InputProps={{
              endAdornment: (
                <InputAdornment
                  className="custom-input-adornment"
                  style={{ color: "var(--border-input-fields)" }}
                  position="end">
                  %
                </InputAdornment>
              ),
            }}
            label="Tax Rate"
            size="small"
            placeholder="25"
            onValueChange={(values) => {
              const { floatValue } = values;
              if (floatValue != null) {
                setErrorTax(false);
                dispatch(changeTaxRate(floatValue / SCALE_PERC));
              } else {
                setErrorTax(true);
                dispatch(changeTaxRate(null));
              }
            }}
          />
        </Tooltip>
        <Tooltip
          placement="right-start"
          arrow
          open={errorWacc}
          title="Invalid number">
          <NumericFormat
            id="wacc-input"
            value={analysisData.wacc * SCALE_PERC}
            decimalScale={1} // 1 decimal place
            decimalSeparator="." // use dot for decimal
            customInput={TextField}
            InputProps={{
              endAdornment: (
                <InputAdornment
                  className="custom-input-adornment"
                  style={{ color: "var(--border-input-fields)" }}
                  position="end">
                  %
                </InputAdornment>
              ),
            }}
            label="Cost of Capital (WACC)"
            size="small"
            placeholder="10"
            onValueChange={(values) => {
              const { floatValue } = values;
              if (floatValue != null) {
                setErrorWacc(false);
                dispatch(changeWacc(floatValue / SCALE_PERC));
              } else {
                setErrorWacc(true);
                dispatch(changeWacc(null));
              }
            }}
          />
        </Tooltip>
        <Tooltip
          placement="right-start"
          arrow
          open={errorG}
          title="Invalid number">
          <NumericFormat
            id="wacc-input"
            value={analysisData.terminalGrowthRate * SCALE_PERC}
            decimalScale={1} // 1 decimal place
            decimalSeparator="." // use dot for decimal
            customInput={TextField}
            InputProps={{
              endAdornment: (
                <InputAdornment
                  className="custom-input-adornment"
                  style={{ color: "var(--border-input-fields)" }}
                  position="end">
                  %
                </InputAdornment>
              ),
            }}
            label="Termial Growth Rate"
            size="small"
            placeholder="0"
            onValueChange={(values) => {
              const { floatValue } = values;
              if (floatValue != null) {
                setErrorG(false);
                dispatch(changeTerminalGrowthRate(floatValue / SCALE_PERC));
              } else {
                setErrorG(true);
                dispatch(changeTerminalGrowthRate(null));
              }
            }}
          />
        </Tooltip>
        <Tooltip
          placement="right-start"
          arrow
          open={errorNrShares}
          title="Invalid number">
          <NumericFormat
            id="wacc-input"
            value={analysisData?.companyData.nrShares / scalingFactor}
            decimalScale={1} // 1 decimal place
            thousandSeparator=","
            decimalSeparator="." // use dot for decimal
            customInput={TextField}
          
            label={`Nr of Shares (${
              scalingFactor === "1000000" ? "Millions" : "Thousands"
            })`}
            size="small"
            placeholder="10"
            onValueChange={(values) => {
              const { floatValue } = values;
              if (floatValue != null) {
                setErrorNrShares(false);
                dispatch(changeNrShares(floatValue * scalingFactor));
              } else {
                setErrorNrShares(true);
                dispatch(changeNrShares(null));
              }
            }}
          />
        </Tooltip>
        <div style={{ display: "flex", gap: "12px" }}>
          <CurrencyCorrectionField
            label="Reporting Currency"
            infoText="The currency this company's financial statements are filed in. Used to convert fundamentals into the trading currency below, for comparison with the market price. Change this if it looks wrong."
            detectedValue={detectedReportingCurrency}
            effectiveValue={effectiveReportingCurrency}
            onChangeOverride={(value) => dispatch(setReportingCurrencyOverride(value))}
            onSaveToDatabase={saveCurrencyCorrection(
              "reportingCurrency",
              setReportingCurrencyOverride
            )}
          />
          <CurrencyCorrectionField
            label="Trading Currency"
            infoText="The currency this stock's price is actually quoted in. Rarely wrong - unlock to edit if it looks incorrect."
            detectedValue={detectedTradingCurrency}
            effectiveValue={effectiveTradingCurrency}
            onChangeOverride={(value) => dispatch(setTradingCurrencyOverride(value))}
            onSaveToDatabase={saveCurrencyCorrection(
              "tradingCurrency",
              setTradingCurrencyOverride
            )}
            locked
          />
        </div>

        {/* <TextField
          type="number"
          size="small"
          placeholder="10"
          label={`Nr of Shares (${
            scalingFactor === "1000000" ? "Millions" : "Thousands"
          })`}
          value={analysisData?.companyData.nrShares / scalingFactor}
          onChange={(e) =>
            dispatch(changeNrShares(e.target.value * scalingFactor))
          }
        /> */}
      </div>
    </div>
  );
}

export default ValuationAssumptions;
