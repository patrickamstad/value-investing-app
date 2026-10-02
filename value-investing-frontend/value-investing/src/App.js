import "./App.css";
import ContentHomePage from "./pages/home/ContentHomePage";
import ContentScreenerPage from "./pages/screener/ContentScreenerPage";
import ContentValuationPage from "./pages/valuation/ContentValuationPage";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { Routes, Route } from "react-router-dom";
import ContentTestingPage from "./pages/testing/ContentTestingPage";
import ContentLoginPage from "./pages/login/ContentLoginPage";
import GoogleCallback from "./pages/login/components/GoogleCallback";
import ContentMCCPage from "./pages/microcapclub/ContentMCCPage";
import ContentScreenerPageNew from "./pages/screener/ContentScreenerPageNew";
import ContentAnalysisPage from "./pages/Analysis/ContentAnalysisPage";
import WatchlistPage from "./pages/watchlist/WatchlistPage";

function App() {
  // define a color theme. These colors will be used throughout the App
  const theme = createTheme({
    typography: {
      // need because we set font-size in App.css to 62.5 % (10 px)
      // htmlFontSize: 10,
    },
  });

  return (
    <>
      <ThemeProvider theme={theme}>
        <Routes>
          <Route path="/" element={<ContentLoginPage />}></Route>
          <Route
            path="/google-auth/callback"
            element={<GoogleCallback />}></Route>
          <Route path="/screener" element={<ContentScreenerPageNew />}></Route>
          {/* <Route path="/valuation" element={<ContentValuationPage />}></Route> */}
          <Route path="/analysis" element={<ContentAnalysisPage />}></Route>
          <Route path="/watchlist" element={<WatchlistPage />}></Route>
          <Route path="/mcc" element={<ContentMCCPage />}></Route>
          <Route path="/testing" element={<ContentTestingPage />}></Route>
        </Routes>
      </ThemeProvider>
    </>
  );
}

export default App;
