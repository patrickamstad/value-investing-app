import React, { useState } from "react";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import { useDispatch, useSelector } from "react-redux";
import ToggleButtonsScaling from "./ToggleButtonsScaling";
import { OutlinedInput } from "@mui/material";
import ValuationApproachSelect from "./ValuationApproachSelect";
import Tooltip from "@mui/material/Tooltip";
import {
  updateValuationData,
  setTableCurrencyMode,
} from "../../../features/analysisSlice";
import {
  computeAto,
  computeEquityVal,
  computeNetOpAssets,
  computeNopatBottomUp,
  computeNopatTopDown,
  computeOpIncomeBottomUp,
  computeOpIncomeTopDown,
  computeOpMarginBottomUp,
  computeRnoa,
} from "./selectorFunctions";
import ValuationAssumptions from "./ValuationAssumptions";
import MetricGraph from "./MetricGraph";
import ValuationSummary from "./ValuationSummary";
import { useLastClosePrice } from "../../valuation/components/AccordionTitle";
import useAxiosWithAuth from "../../../axios/useAxiosWithAuth";
import LiquidationValue from "./LiquidationValue";
import GlassCardWrapper from "./GlassCardWrapper";
import SaveValuationModal from "./SaveValuationModal";
import ValuationActionToolbar from "./ValuationActionToolbar";
import NumericTableCell from "./NumericTableCell";
import PercentageTableCell from "./PercentageTableCell";
import NumericTableCellInput from "./NumericTableCellInput";
import PercentageTableCellInput from "./PercentageTableCellInput";

const valuationCases = ["BEAR", "BASE", "BULL"];
const topDownEditableFields = ["revenue", "op_margins"];
const bottomUpEditableFields = ["revenue", "cogs", "sga", "rnd", "other_opex"];
const editableFieldsCapitalStructure = [
  "operatingAssets",
  "operatingLiabilities",
  "bookValue",
];
// Fields tagged type "absolute" in the backend response that are NOT monetary
// amounts (a share count and a turnover multiple, respectively) - must never be
// rescaled by the fundamentals table's currency toggle.
const NON_MONETARY_ABSOLUTE_FIELDS = ["nrShares", "ato"];

function ValuationModel({ qfsSymbol, onToggleHistory, isHistoryOpen }) {
  const companyData = useSelector((state) => state.analysis?.companyData);
  const valuationApproach = useSelector(
    (state) => state.analysis?.valuationApproach
  );
  const axiosInstanceAuth = useAxiosWithAuth();

  const valuationData = useSelector((state) => state.analysis?.valuationData);
  const taxRate = useSelector((state) => state.analysis?.taxRate);
  const wacc = useSelector((state) => state.analysis?.wacc);
  const g = useSelector((state) => state.analysis?.terminalGrowthRate);
  const nrShares = useSelector(
    (state) => state.analysis?.companyData?.nrShares
  );
  const { data, isLoading } = useLastClosePrice(qfsSymbol, axiosInstanceAuth);

  const currencyCode = useSelector(
    (state) => state.analysis?.companyData?.currency
  );
  const tableCurrencyMode = useSelector(
    (state) => state.analysis?.tableCurrencyMode
  );
  const fxRate = useSelector((state) => state.analysis?.companyData?.fxRate);
  const reportingCurrencyCode = useSelector(
    (state) => state.analysis?.companyData?.reportingCurrency
  );

  const [scaling, setScaling] = useState("1000000");
  const [scalingBalanceSheet, setScalingBalanceSheet] = useState("1000000");
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);

  const dispatch = useDispatch();

  const handleToggleButtonChange = (e, newValue) => {
    // null check enforces that always one value is selected
    if (newValue !== null) {
      setScaling(newValue);
    }
  };

  const handleScalingChangeBs = (e, newValue) => {
    // null check enforces that always one value is selected
    if (newValue !== null) {
      setScalingBalanceSheet(newValue);
    }
  };

  const handleValuationChange = (
    value,
    metricName,
    valuationCase,
    scaleFactor
  ) => {
    dispatch(
      updateValuationData({
        newValue: value,
        metricName: metricName,
        caseIndex: valuationCase,
        scaleFactor: scaleFactor,
      })
    );
  };

  // Historical/TTM table cells only (never the editable BEAR/BASE/BULL columns,
  // which always stay in trading currency). Mirrors the original values[period]
  // truthy-check fallback to "-" exactly, just rescaling monetary values on top
  // when the user has switched the table to reporting-currency display.
  const getTableCellValue = (metricName, values, period) => {
    const rawValue = values?.values?.[period];
    if (!rawValue) return "-";
    const isMonetary =
      values?.type === "absolute" &&
      !NON_MONETARY_ABSOLUTE_FIELDS.includes(metricName);
    return isMonetary && tableCurrencyMode === "reporting" && fxRate
      ? rawValue / fxRate
      : rawValue;
  };

  let opIncome = [0, 0, 0];
  let nopat = [0, 0, 0];
  let opMargins = [0, 0, 0];
  let equityVal = [0, 0, 0];
  let netOpAssets = [0, 0, 0];
  let rnoa = [0, 0, 0];
  let ato = [0, 0, 0];

  if (valuationApproach === "topDown") {
    //compute metrics for bear, base, bull
    for (let i = 0; i < valuationCases.length; i++) {
      opIncome[i] = computeOpIncomeTopDown(valuationData, i);
      nopat[i] = computeNopatTopDown(valuationData, taxRate, i);
    }
  } else if (valuationApproach === "bottomUp") {
    for (let i = 0; i < valuationCases.length; i++) {
      //bottomUp we need to compute OpIncome, OpMargin and nopat
      opIncome[i] = computeOpIncomeBottomUp(valuationData, i);

      //compute op margin
      opMargins[i] = computeOpMarginBottomUp(valuationData, i);

      //compute NOPAT
      nopat[i] = computeNopatBottomUp(valuationData, taxRate, i);
    }
  }

  //compute equity val, netOperating assets, rnoa, asset turnover
  for (let i = 0; i < valuationCases.length; i++) {
    equityVal[i] = computeEquityVal(
      valuationData?.bookValue,
      nopat,
      wacc,
      valuationData?.netOperatingAssets,
      g,
      i
    );

    netOpAssets[i] = computeNetOpAssets(valuationData, i);
    rnoa[i] = computeRnoa(nopat[i], netOpAssets[i], taxRate);
    ato[i] = computeAto(valuationData, i);
  }

  return (
    <>
      <div className="valuation-model-grip-wrapper">
        <ValuationSummary
          equityVals={equityVal}
          currencyCode={currencyCode}
          lastClosePrice={data?.lastClosePrice}
          nrShares={nrShares}
          qfsSymbol={qfsSymbol}
        />
        <ValuationAssumptions scalingFactor={scaling} />
      </div>
      <ValuationActionToolbar
        scaling={scaling}
        onScalingChange={handleToggleButtonChange}
        onSave={() => setIsSaveModalOpen(true)}
        onToggleHistory={onToggleHistory}
        isHistoryOpen={isHistoryOpen}
      />
      <GlassCardWrapper
        title="Valuation Model"
        currencyCode={currencyCode}
        qfsSymbol={qfsSymbol}
        lastClosePrice={data?.lastClosePrice}
        tableCurrencyMode={tableCurrencyMode}
        onTableCurrencyModeChange={(value) => dispatch(setTableCurrencyMode(value))}
        tradingCurrencyCode={currencyCode}
        reportingCurrencyCode={reportingCurrencyCode}>
        <TableContainer
          component={Paper}
          sx={{
            backgroundColor: "transparent",
            boxShadow: "none",
            borderRadius: "20px",
            marginTop: "12px",
          }}
          className="custom-mui-table">
          <Table
            sx={{ minWidth: 650 }}
            size="small"
            aria-label="simple table"
            className="custom-table-analysis-page">
            <TableHead className="custom-table-head">
              <TableRow>
                <TableCell>LINE ITEM</TableCell>
                {companyData?.periods?.map((period) => {
                  return <TableCell>{period}</TableCell>;
                })}
                {valuationCases?.map((item) => {
                  return <TableCell align="left">{item}</TableCell>;
                })}
              </TableRow>
            </TableHead>
            <TableBody className="custom-table-body-val-model">
              <TableRow>
                <TableCell className="valuation-model-title-row" colSpan={10}>
                  <div className="flex-box-wrapper-table-header-val-model">
                    <span> NOPAT DERIVATION</span>
                  </div>
                </TableCell>
              </TableRow>
              {Object.entries(companyData?.metricsNopat).map(
                ([metricName, values]) => (
                  <TableRow
                    key={metricName}
                    className={
                      values.fontStyle === "italic" ? "computed-row" : ""
                    }>
                    <TableCell>
                      <div className="flexbox-wrapper-table-cell-analysis">
                        {values.label ? values.label : metricName}
                        {/* display graph if time series data is available */}
                        {values.hasTs && (
                          <MetricGraph
                            data={values.ts}
                            metricName={
                              values.label ? values.label : metricName
                            }
                          />
                        )}
                      </div>
                    </TableCell>
                    {companyData?.periods.map((period) => {
                      let cellValue = getTableCellValue(metricName, values, period);

                      //based on the value type we return different cell in order to format differently
                      if (values?.type === "perc") {
                        return (
                          <PercentageTableCell
                            cellValue={cellValue}
                            scalingFactor={100}
                          />
                        );
                      } else if (values?.type === "absolute") {
                        return (
                          <NumericTableCell
                            cellValue={cellValue}
                            scalingFactor={scaling}
                          />
                        );
                      }
                    })}
                    {valuationCases.map((valuationCase, index) => {
                      let isEditable = false;
                      let isVisible = false;
                      if (valuationApproach === "topDown") {
                        isEditable = topDownEditableFields.includes(metricName);
                        isVisible = values.topDownVisible;
                      } else {
                        isEditable =
                          bottomUpEditableFields.includes(metricName);
                        isVisible = values.bottomUpVisible;
                      }

                      if (!isVisible) {
                        return;
                      }

                      let scaleFactor = values.type !== "ratio" ? scaling : 1;

                      var value = valuationData[metricName]?.[index];

                      switch (metricName) {
                        case "operating_income":
                          // if (valuationApproach === "topDown") {
                          value = opIncome[index];
                          // }

                          break;
                        case "NOPAT":
                          value = nopat[index];
                          break;
                        case "op_margins":
                          //if valuation approach is topDown, op margin will be input by user; for bottomUp it will be computed
                          if (valuationApproach === "bottomUp") {
                            value = opMargins[index];
                          }
                          break;
                        case "income_tax":
                          //compute the income tax
                          value = opIncome[index] * taxRate;
                          break;
                        case "eff_tax_rate":
                          value = taxRate;
                          break;
                      }
                      if (values?.type === "absolute") {
                        return (
                          <NumericTableCellInput
                            value={value}
                            scalingFactor={scaleFactor}
                            metricName={metricName}
                            isEditable={isEditable}
                            valuationCase={index}
                            handleChange={handleValuationChange}
                          />
                        );
                      } else if (values?.type === "perc") {
                        return (
                          <PercentageTableCellInput
                            value={value}
                            scalingFactor={scaleFactor}
                            metricName={metricName}
                            isEditable={isEditable}
                            valuationCase={index}
                            handleChange={handleValuationChange}
                          />
                        );
                      }
                    })}
                  </TableRow>
                )
              )}
              <TableRow>
                <TableCell className="valuation-model-title-row" colSpan={10}>
                  <div
                    className="flex-box-wrapper-table-header-val-model valuation-model-title-row"
                    style={{ fontSize: "0.75rem" }}>
                    <span>INVESTED CAPITAL (NOA)</span>
                  </div>
                </TableCell>
              </TableRow>
              {Object.entries(companyData?.metricsNoa).map(
                ([metricName, values]) => {
                  return (
                    <TableRow
                      key={metricName}
                      className={
                        values.fontStyle === "italic" ? "computed-row" : ""
                      }>
                      <TableCell>
                        <div className="flexbox-wrapper-table-cell-analysis">
                          {values.label ? values.label : metricName}{" "}
                          {/* display graph if time series data is available */}
                          {values.hasTs && (
                            <MetricGraph
                              data={values.ts}
                              metricName={
                                values.label ? values.label : metricName
                              }
                            />
                          )}
                        </div>
                      </TableCell>
                      {companyData?.periods.map((period) => {
                        let cellValue = getTableCellValue(metricName, values, period);

                        if (values?.type === "perc") {
                          return (
                            <PercentageTableCell
                              cellValue={cellValue}
                              scalingFactor={100}
                            />
                          );
                        } else if (values?.type === "absolute") {
                          return (
                            <NumericTableCell
                              cellValue={cellValue}
                              scalingFactor={scaling}
                            />
                          );
                        }
                      })}
                      {valuationCases.map((valuationCase, index) => {
                        let isEditable =
                          editableFieldsCapitalStructure.includes(metricName);
                        let scaleFactor = values.type !== "ratio" ? scaling : 1;

                        var value = valuationData[metricName]?.[index];

                        switch (metricName) {
                          case "netOperatingAssets":
                            // if (valuationApproach === "topDown") {
                            value = netOpAssets[index];
                            // }

                            break;
                        }

                        if (values?.type === "absolute") {
                          return (
                            <NumericTableCellInput
                              value={value}
                              scalingFactor={scaleFactor}
                              metricName={metricName}
                              isEditable={isEditable}
                              valuationCase={index}
                              handleChange={handleValuationChange}
                            />
                          );
                        } else if (values?.type === "perc") {
                          return (
                            <PercentageTableCellInput
                              value={value}
                              scalingFactor={scaleFactor}
                              metricName={metricName}
                              isEditable={isEditable}
                              valuationCase={index}
                              handleChange={handleValuationChange}
                            />
                          );
                        }
                      })}
                    </TableRow>
                  );
                }
              )}
              <TableRow>
                <TableCell className="valuation-model-title-row" colSpan={10}>
                  <div className="flex-box-wrapper-table-header-val-model">
                    <span>VALUATION DRIVERS</span>
                  </div>
                </TableCell>
              </TableRow>
              {Object.entries(companyData?.metricsValDrivers).map(
                ([metricName, values]) => {
                  return (
                    <TableRow key={metricName}>
                      <TableCell>
                        <div className="flexbox-wrapper-table-cell-analysis">
                          {values.label ? values.label : metricName}{" "}
                          {/* display graph if time series data is available */}
                          {values.hasTs && (
                            <MetricGraph
                              data={values.ts}
                              metricName={
                                values.label ? values.label : metricName
                              }
                            />
                          )}
                        </div>
                      </TableCell>
                      {companyData?.periods.map((period) => {
                        let cellValue = getTableCellValue(metricName, values, period);

                        //check if metric is asset turnover
                        const isAto = metricName === "ato";

                        if (values?.type === "perc") {
                          return (
                            <PercentageTableCell
                              cellValue={cellValue}
                              scalingFactor={100}
                            />
                          );
                        } else if (values?.type === "absolute") {
                          return (
                            <NumericTableCell
                              cellValue={cellValue}
                              scalingFactor={scaling}
                              {...(isAto && {
                                decimalPlaces: 2,
                                suffix: "x",
                                scalingFactor: 1,
                              })}
                            />
                          );
                        }
                      })}
                      {valuationCases.map((valuationCase, index) => {
                        let isEditable =
                          editableFieldsCapitalStructure.includes(metricName);
                        let scaleFactor = values.type !== "ratio" ? scaling : 1;

                        //check if metric is asset turnover
                        const isAto = metricName === "ato";

                        var value = valuationData[metricName]?.[index];

                        switch (metricName) {
                          case "rnoa":
                            value = rnoa[index];
                            break;
                          case "ato":
                            value = ato[index];
                            break;
                        }

                        if (values?.type === "absolute") {
                          return (
                            <NumericTableCellInput
                              value={value}
                              scalingFactor={scaleFactor}
                              metricName={metricName}
                              isEditable={isEditable}
                              valuationCase={index}
                              handleChange={handleValuationChange}
                              {...(isAto && {
                                decimalPlaces: 2,
                                suffix: "x",
                                scalingFactor: 1,
                              })}
                            />
                          );
                        } else if (values?.type === "perc") {
                          return (
                            <PercentageTableCellInput
                              value={value}
                              scalingFactor={scaleFactor}
                              metricName={metricName}
                              isEditable={isEditable}
                              valuationCase={index}
                              handleChange={handleValuationChange}
                            />
                          );
                        }
                      })}
                    </TableRow>
                  );
                }
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </GlassCardWrapper>
      <LiquidationValue
        qfsSymbol={qfsSymbol}
        scaling={scalingBalanceSheet}
        handleToggleButtonChange={handleScalingChangeBs}
        currencyCode={currencyCode}
        lastClosePrice={data?.lastClosePrice}
        nrShares={nrShares}
      />

      <SaveValuationModal
        open={isSaveModalOpen}
        onClose={() => setIsSaveModalOpen(false)}
        qfsSymbol={qfsSymbol}
        equityVals={equityVal}
      />
    </>
  );
}

export default ValuationModel;
