import React from "react";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import Collapse from "@mui/material/Collapse";
import { OutlinedInput } from "@mui/material";

function AssetValLineItem({
  open,
  label,
  value,
  metric,
  handleChange,
  multiplier,
  handleMultiplierChange,
  category,
  scaling = 1,
  displayDivisor = 1,
  disabled = false,
}) {
  return (
    <TableRow className={`custom-table-row ${open ? "open" : ""}`}>
      <TableCell className={`custom-cell ${open ? "" : "no-padding-cell"}`}>
        <Collapse in={open} timeout="auto" unmountOnExit>
          <span style={{ marginLeft: "54px" }}>{label}</span>
        </Collapse>
      </TableCell>
      <TableCell
        align="right"
        className={`custom-cell ${open ? "" : "no-padding-cell"}`}>
        <Collapse in={open} timeout="auto" unmountOnExit>
          <OutlinedInput
            onChange={(e) => handleChange(e, category, metric)}
            type="number"
            value={(value / scaling / displayDivisor).toFixed(0)}
            disabled={disabled}
            size="small"
            className="custom-input-valuation-table liquidation-value"
          />
        </Collapse>
      </TableCell>
      <TableCell
        align="right"
        className={`custom-cell ${open ? "" : "no-padding-cell"}`}>
        <Collapse in={open} timeout="auto" unmountOnExit>
          <OutlinedInput
            value={multiplier}
            onChange={(e) => handleMultiplierChange(e, category, metric)}
            disabled={disabled}
            type="number"
            size="small"
            className="custom-input-valuation-table liquidation-value"
          />
        </Collapse>
      </TableCell>
      <TableCell
        align="right"
        className={`custom-cell ${open ? "" : "no-padding-cell"}`}>
        {" "}
        <Collapse in={open} timeout="auto" unmountOnExit>
          {((multiplier * value) / scaling / displayDivisor).toFixed(0)}
        </Collapse>
      </TableCell>
    </TableRow>
  );
}

export default AssetValLineItem;
