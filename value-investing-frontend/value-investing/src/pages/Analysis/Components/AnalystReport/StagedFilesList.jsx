import React from "react";
import {
  List, ListItem, Typography, Divider, Box,
  FormControl, InputLabel, Select, MenuItem, IconButton,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";

export const DOCUMENT_TYPE_OPTIONS = [
  { value: "auto",                  label: "Auto-detect" },
  { value: "annual_report",         label: "Annual Report" },
  { value: "quarterly_report",      label: "Quarterly Report" },
  { value: "earnings_call",         label: "Earnings Call" },
  { value: "investor_presentation", label: "Investor Presentation" },
  { value: "analyst_report",        label: "Analyst Report" },
  { value: "news_article",          label: "News Article" },
  { value: "other",                 label: "Other" },
];

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StagedFilesList({ files, onRemove, documentTypes, onTypeChange }) {
  if (files.length === 0) {
    return (
      <Typography sx={{ color: "var(--text-color-grey-scale)", fontSize: "0.85rem", mt: 2 }}>
        No files staged yet.
      </Typography>
    );
  }

  return (
    <>
      <Typography sx={{ color: "var(--text-color-grey-scale)", fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.08em", mt: 2, mb: 1 }}>
        READY TO PROCESS
      </Typography>
      <List disablePadding>
      {files.map((file, index) => (
        <React.Fragment key={file.id}>
          <ListItem disablePadding sx={{ py: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", width: "100%", gap: 1.5 }}>
              <PictureAsPdfOutlinedIcon sx={{ color: "var(--action-color)", flexShrink: 0 }} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ color: "var(--header-color)", fontSize: "0.9rem" }} noWrap>
                  {file.name}
                </Typography>
                <Typography sx={{ color: "var(--text-color-grey-scale)", fontSize: "0.75rem" }}>
                  {formatBytes(file.size)}
                </Typography>
              </Box>
              <FormControl size="small" sx={{ minWidth: 175, flexShrink: 0 }}>
                <InputLabel id={`doc-type-label-${file.id}`} className="custom-label-val-model">
                  Document Type
                </InputLabel>
                <Select
                  className="custom-select-val-model"
                  labelId={`doc-type-label-${file.id}`}
                  label="Document Type"
                  value={documentTypes[file.id] ?? "auto"}
                  onChange={(e) => onTypeChange(file.id, e.target.value)}>
                  {DOCUMENT_TYPE_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <IconButton
                size="small"
                onClick={() => onRemove(file.id)}
                sx={{ color: "var(--error-red)", flexShrink: 0 }}>
                <DeleteOutlineIcon />
              </IconButton>
            </Box>
          </ListItem>
          {index < files.length - 1 && (
            <Divider sx={{ borderColor: "var(--border-glass-card)" }} />
          )}
        </React.Fragment>
      ))}
      </List>
    </>
  );
}

export default StagedFilesList;
