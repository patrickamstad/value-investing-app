import React, { useState } from "react";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import AssetValCollapsableHeader from "../../valuation/components/AssetValCollapsableHeader";
import { useDispatch, useSelector } from "react-redux";
import {
  computeSumBalanceSheet,
  computeTotalAssets,
  sumBalanceSheetItems,
} from "../../valuation/components/selectorFunctions";
import AssetValLineItem from "../../valuation/components/AssetValLineItem";
import {
  updateLiquidationValuationData,
  updateLiqValMultChange,
} from "../../../features/analysisSlice";
import { computeTotAssets } from "./selectorFunctions";

// const tableColumnWidths = ["30%", "25%", "20%", "25%"];

function AssetTable({
  qfsSymbol,
  tableColumnWidths,
  scaling,
  displayDivisor = 1,
  disabled = false,
}) {
  const [openAsset, setOpenAssets] = useState(true);
  const [openCurrentAsset, setOpenCurrentAsset] = useState(false);
  const [openNonCurrentAssets, setOpenNonCurrentAssets] = useState(false);
  const balanceSheet = useSelector((state) => state.analysis?.balanceSheet);
  //   const [openLiab, setOpenLiab] = useState(true);
  //   const [openCurrentLiab, setOpenCurrentLiab] = useState(false);
  //   const [openNonCurrentLiab, setOpenNonCurrentLiab] = useState(false);

  const dispatch = useDispatch();

  const handleAssetClick = () => {
    //if total assets are closed also close current assets
    if (openCurrentAsset) {
      setOpenCurrentAsset(false);
    }

    //if total assets are closed also close non-current assets
    if (openNonCurrentAssets) {
      setOpenNonCurrentAssets(false);
    }
    setOpenAssets(!openAsset);
  };

  const handleCurrentAssetClick = () => {
    setOpenCurrentAsset(!openCurrentAsset);
  };

  const handleNonCurrentAssetClick = () => {
    setOpenNonCurrentAssets(!openNonCurrentAssets);
  };

  const totalCurrentAssets = useSelector(
    (state) => sumBalanceSheetItems(state.analysis?.balanceSheet?.currentAssets)
    // computeSumBalanceSheet(
    //   state.valuation.assetValuations?.find(
    //     (item) => item.qfsSymbol === qfsSymbol
    //   ),
    //   "currentAssets"
    // )
  );

  const totalNonCurrentAssets = useSelector(
    (state) =>
      sumBalanceSheetItems(state.analysis?.balanceSheet?.nonCurrentAssets)

    // computeSumBalanceSheet(
    //   state.valuation.assetValuations?.find(
    //     (item) => item.qfsSymbol === qfsSymbol
    //   ),
    //   "nonCurrentAssets"
    // )
  );

  const totalAssets = useSelector((state) =>
    // computeTotalAss
    computeTotAssets(state.analysis?.balanceSheet)
  );

  const handleMetricChange = (e, category, metric) => {
    const newValue = e.target.value;

    console.log("metric change asset val: qfsSymbol: ", qfsSymbol);
    console.log("metric change asset val: category: ", category);
    console.log("metric change asset val: metric: ", metric);
    console.log("metric change asset val: newValue: ", newValue);

    dispatch(
      updateLiquidationValuationData(category, metric, newValue * scaling)
    );
  };

  const handleMultiplierChange = (e, category, metric) => {
    const newValue = e.target.value;

    console.log("metric change asset val: qfsSymbol: ", qfsSymbol);
    console.log("metric change asset val: category: ", category);
    console.log("metric change asset val: metric: ", metric);
    console.log("metric change asset val: newValue: ", newValue);

    dispatch(updateLiqValMultChange({ category, metric, newValue }));
  };

  return (
    <TableContainer
      component={Paper}
      sx={{
        backgroundColor: "transparent",
        boxShadow: "none",
        borderRadius: "20px",
        // marginTop: "12px",
        height: "fit-content",
      }}
      className="custom-mui-table">
      <Table size="small" aria-label="simple table">
        <TableHead className="custom-table-head">
          <TableRow>
            <TableCell style={{ width: tableColumnWidths[0] }}></TableCell>
            <TableCell style={{ width: tableColumnWidths[1] }} align="right">
              2025-06-12
            </TableCell>
            <TableCell style={{ width: tableColumnWidths[2] }} align="right">
              Multiplier
            </TableCell>
            <TableCell style={{ width: tableColumnWidths[3] }} align="right">
              Value
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <AssetValCollapsableHeader
            label="Total Assets"
            columnWidths={tableColumnWidths}
            handleClick={handleAssetClick}
            open={openAsset}
            openCollapse={true} //highest level cannot be collapsed
            hasCellPadding={true}
            marginLeft=""
            titleType="big"
            value={(totalAssets / scaling / displayDivisor).toFixed(0)}
          />
          <AssetValCollapsableHeader
            label="Current Assets"
            columnWidths={tableColumnWidths}
            handleClick={handleCurrentAssetClick}
            open={openCurrentAsset}
            openCollapse={openAsset}
            hasCellPadding={openAsset ? true : false}
            marginLeft="10px"
            value={(totalCurrentAssets / scaling / displayDivisor).toFixed(0)}
          />
          {balanceSheet?.currentAssets?.map((lineItem) => {
            return (
              <AssetValLineItem
                handleChange={handleMetricChange}
                key={lineItem.metric}
                multiplier={lineItem.multiplier}
                open={openCurrentAsset}
                handleMultiplierChange={handleMultiplierChange}
                label={lineItem.label}
                value={lineItem.value}
                category="currentAssets"
                metric={lineItem.metric}
                scaling={scaling}
                displayDivisor={displayDivisor}
                disabled={disabled}
              />
            );
          })}
          <AssetValCollapsableHeader
            label="Non-Current Assets"
            columnWidths={tableColumnWidths}
            handleClick={handleNonCurrentAssetClick}
            open={openNonCurrentAssets}
            openCollapse={openAsset}
            hasCellPadding={openAsset ? true : false}
            marginLeft="10px"
            value={(totalNonCurrentAssets / scaling / displayDivisor).toFixed(0)}
          />
          {balanceSheet?.nonCurrentAssets?.map((lineItem) => {
            return (
              <AssetValLineItem
                handleChange={handleMetricChange}
                key={lineItem.metric}
                multiplier={lineItem.multiplier}
                open={openNonCurrentAssets}
                handleMultiplierChange={handleMultiplierChange}
                label={lineItem.label}
                value={lineItem.value}
                category="nonCurrentAssets"
                metric={lineItem.metric}
                scaling={scaling}
                displayDivisor={displayDivisor}
                disabled={disabled}
              />
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default AssetTable;
