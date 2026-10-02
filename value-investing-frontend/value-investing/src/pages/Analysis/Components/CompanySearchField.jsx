import React, { useCallback, useEffect } from "react";
import Autocomplete from "@mui/material/Autocomplete";
import { useDispatch, useSelector } from "react-redux";
import { VariableSizeList } from "react-window";
import TextField from "@mui/material/TextField";
import useAxiosWithAuth from "../../../axios/useAxiosWithAuth";
import { initializeTickerSymbols } from "../../../features/valuationSlice";
import Chip from "@mui/material/Chip";
import {
  initalizeBalanceSheet,
  initializeCompanyData,
  initializeSavedModels,
  initializeTickerSymbol,
  initializeValuationData,
  setSelectedModel,
} from "../../../features/analysisSlice";
import { useSnackbar } from "../../GlobalComponents/SnackbarProvider";
import { clearHistory } from "src/features/watchlistSlice";
import { fetchValuationHistory } from "src/features/valuationHistorySlice";

const LISTBOX_PADDING = 8; // px

// Custom listbox using react-window
const ListboxComponent = React.forwardRef(function ListboxComponent(
  props,
  ref
) {
  const { children, ...other } = props;
  const itemData = React.Children.toArray(children);
  const itemCount = itemData.length;

  function getHeight(index) {
    return 48; // Fixed height for each option
  }

  return (
    <div ref={ref} {...other}>
      <VariableSizeList
        height={250} // Adjust dropdown height
        width="100%"
        itemSize={getHeight}
        itemCount={itemCount}>
        {({ index, style }) => (
          <div style={{ ...style, top: style.top + LISTBOX_PADDING }}>
            {itemData[index]}
          </div>
        )}
      </VariableSizeList>
    </div>
  );
});

function CompanySearchField({ setBackdropLoading }) {
  const analysisState = useSelector((state) => state.analysis);
  const tickerSymbols = useSelector((state) => state.valuation.tickerSymbols);

  const dispatch = useDispatch();
  const axiosInstanceAuth = useAxiosWithAuth();

  const { showMessage } = useSnackbar();

  const fetchTickerData = useCallback(
    (qfsSymbol, reportingCurrencyOverride, tradingCurrencyOverride) => {
      if (!qfsSymbol) return;

      const currencyOverrideParams = {
        ...(reportingCurrencyOverride
          ? { reportingCurrency: reportingCurrencyOverride }
          : {}),
        ...(tradingCurrencyOverride
          ? { tradingCurrency: tradingCurrencyOverride }
          : {}),
      };

      setBackdropLoading(true);

      // --- main analysis data ---
      axiosInstanceAuth
        .get(`screener/analysis/${qfsSymbol}/`, {
          params: currencyOverrideParams,
        })
        .then((response) => {
          dispatch(initializeCompanyData(response.data));
          dispatch(initializeValuationData(response?.data?.valuationDefaults));
        })
        .catch((error) => {
          showMessage(`Error fetching data: ${error}`, "error");
          console.error("ERROR: GET screener/analysis/: ", error);
        })
        .finally(() => setBackdropLoading(false));

      // --- balance sheet (liquidation value) ---
      axiosInstanceAuth
        .post("/screener/asset-val-fundamentals/", {
          qfs_symbols: [qfsSymbol],
          ...currencyOverrideParams,
        })
        .then((response) => {
          dispatch(initalizeBalanceSheet(response.data[0]?.data));
        })
        .catch((error) => {
          showMessage(`Error computing asset val ${error}`, "error");
          console.error(
            "ERROR: POST /screener/asset-val-fundamentals/: ",
            error
          );
        });

      // --- valuation history ---
      dispatch(clearHistory());
      dispatch(fetchValuationHistory({ ticker: qfsSymbol }));

      // --- saved valuation models ---
      axiosInstanceAuth
        .get("/screener/valuation-model/", { params: { qfsSymbol } })
        .then((response) => {
          dispatch(initializeSavedModels(response.data));
          dispatch(setSelectedModel({ isNew: true }));
        })
        .catch((error) =>
          console.error("ERROR: GET /screener/valuation-model/: ", error)
        );
    },
    [axiosInstanceAuth, dispatch, setBackdropLoading, showMessage]
  );

  useEffect(() => {
    const qfsSymbol = analysisState.selectedTickerSymbol?.qfs_symbol;
    if (qfsSymbol) {
      fetchTickerData(
        qfsSymbol,
        analysisState.reportingCurrencyOverride,
        analysisState.tradingCurrencyOverride
      );
    }
  }, [
    analysisState.selectedTickerSymbol,
    analysisState.reportingCurrencyOverride,
    analysisState.tradingCurrencyOverride,
  ]);

  const handleChange = (event, newValue) => {
    dispatch(initializeTickerSymbol(newValue));
  };

  useEffect(() => {
    axiosInstanceAuth
      .get("/screener/get-ticker-symbols/")
      .then((response) => {
        dispatch(initializeTickerSymbols(response.data.data));
      })
      .catch((error) => {
        console.error("ERROR: GET /screener/get-ticker-symbols/: ", error);
      });
  }, []);

  return (
    <div>
      <Autocomplete
        value={analysisState.selectedTickerSymbol}
        options={tickerSymbols}
        ListboxComponent={ListboxComponent}
        onChange={handleChange}
        className="custom-autocomplete-analysis-page"
        getOptionLabel={(option) => `${option.qfs_symbol} - ${option.name}`}
        renderInput={(params) => (
          <TextField
            {...params}
            size="small"
            label="Select an item"
            name="tickers"
          />
        )}
      />
    </div>
  );
}

export default CompanySearchField
