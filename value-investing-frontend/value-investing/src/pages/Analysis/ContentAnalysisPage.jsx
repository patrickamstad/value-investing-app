import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useSelector } from "react-redux";
import { Box } from "@mui/material";

import Layout from "../GlobalComponents/Layout";
import BackdropLoading from "../GlobalComponents/BackdropLoading";
import CompanySearchField from "./Components/CompanySearchField";
import AnalysisTabs from "./Components/AnalysisTabs";
import CompanyOverview from "./Components/CompanyOverview";
import ValuationModel from "./Components/ValuationModel";
import AnalysisHistorySidebar from "./Components/AnalysisHistorySidebar";
import AnalystReport from "./Components/AnalystReport/AnalystReport";

function ContentAnalysisPage() {
  const analysisState = useSelector((state) => state.analysis);
  const [backDropLoading, setBackDropLoading] = useState(false);
  const location = useLocation();
  const [tab, setTab] = useState(0);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (location.state?.initialTab !== undefined) {
      setTab(location.state.initialTab);
    }
  }, [location.state]);

  return (
    <>
      <Layout>
        <main className="main-content-wrapper relative-position">
          <div
            className="flex-wrapper-main-content"
            style={{ overflowX: "auto", paddingTop: "16px" }}>
            <CompanySearchField setBackdropLoading={setBackDropLoading} />

            {analysisState.selectedTickerSymbol && (
              <Box
                sx={{
                  display: "flex",
                  width: "100%",
                  alignItems: "flex-start",
                }}>
                {/* === MAIN CONTENT === */}
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <AnalysisTabs tab={tab} setTab={setTab} />

                  {tab === 0 && <CompanyOverview />}


                  {tab === 1 && (
                    <ValuationModel
                      qfsSymbol={
                        analysisState?.selectedTickerSymbol?.qfs_symbol
                      }
                      onToggleHistory={() => setShowHistory((prev) => !prev)}
                      isHistoryOpen={showHistory}
                    />
                  )}

                  {tab === 2 && <AnalystReport />}

                </Box>

                {/* === HISTORY SIDEBAR === */}
                <AnalysisHistorySidebar
                  isOpen={showHistory}
                  qfsSymbol={analysisState?.selectedTickerSymbol?.qfs_symbol}
                  onClose={() => setShowHistory(false)}
                />
              </Box>
            )}
          </div>
        </main>
      </Layout>
      <BackdropLoading open={backDropLoading} />
    </>
  );
}

export default ContentAnalysisPage;
