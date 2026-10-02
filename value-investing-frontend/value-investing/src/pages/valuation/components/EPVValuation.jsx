import React from "react";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import LineGraph from "./LineGraph";
import ValuationSubCard from "./ValuationSubCard";

function EPVValuation({ epvObject }) {
  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <div className="child-accordion-title"> EPV Valuation </div>
      </AccordionSummary>
      <AccordionDetails>
        <div className="section-title">Prices</div>
        <div className="flexwrapper-price-details">
          <ValuationSubCard
            title="EPV per share (TTM)"
            value={epvObject.epv_per_share_ttm}
            currency={epvObject.epv_currency}
            rounding={2}
          />
          <ValuationSubCard
            title="EPV per share"
            value={epvObject.epv_per_share}
            currency={epvObject.epv_currency}
            rounding={2}
          />
          <ValuationSubCard
            title="Current Price"
            value={epvObject.current_price}
            currency={epvObject.price_currency}
            rounding={2}
          />
        </div>
        <div style={{ display: "flex", gap: "22px" }}>
          <div>
            <div className="section-title">Revenues</div>
            <div style={{ display: "flex", gap: "8px" }}>
              <ValuationSubCard
                title="Revenue (TTM)"
                value={epvObject.revenue_ttm}
                currency={epvObject.epv_currency}
                rounding={1}
              />
              <ValuationSubCard
                title="Revenue (Avg)"
                value={epvObject.avg_revenue}
                currency={epvObject.epv_currency}
                rounding={1}
              />
            </div>
          </div>
          <div>
            <div className="section-title">Operating Margins</div>
            <div style={{ display: "flex", gap: "8px" }}>
              <ValuationSubCard
                title="Operating Margin (TTM)"
                value={epvObject.avg_op_margin_ttm}
                rounding={2}
              />
              <ValuationSubCard
                title="Operating Margin (Avg)"
                value={epvObject.avg_op_margin}
                rounding={2}
              />
            </div>
          </div>
        </div>
        <div className="line-graph-wrapper">
          <div className="graph-title">
            <div>Revenue</div>
          </div>
          <LineGraph
            data={[
              {
                id: "Revenue",
                data: epvObject.revenue_trend,
              },
            ]}
          />
        </div>
        <div className="line-graph-wrapper">
          <div className="graph-title">
            <div>Gross Margin</div>
          </div>
          <LineGraph
            // legendYAxis="Revenue"
            // legendXAxis="Date"
            data={[
              {
                id: "GrossMargin",
                // color: "hsl(224, 70%, 50%)",
                data: epvObject.gross_margin_trend,
              },
            ]}
          />
        </div>
        <div className="line-graph-wrapper">
          <div className="graph-title">
            <div>Operating Margin</div>
          </div>
          <LineGraph
            // legendYAxis="Revenue"
            // legendXAxis="Date"
            data={[
              {
                id: "OperatingMargin",
                // color: "hsl(224, 70%, 50%)",
                data: epvObject.operating_margin_trend,
              },
            ]}
          />
        </div>
        <div className="line-graph-wrapper">
          <div className="graph-title">
            <div>Operating Expenses</div>
          </div>
          <LineGraph
            // legendYAxis="Revenue"
            // legendXAxis="Date"
            data={[
              {
                id: "OperatingExpenses",
                color: "hsl(224, 70%, 50%)",
                data: epvObject.total_opex_trend,
              },
            ]}
          />
        </div>
      </AccordionDetails>
    </Accordion>
  );
}

export default EPVValuation;
