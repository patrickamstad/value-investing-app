import React, { useState } from "react";
import { TextField, MenuItem, Button } from "@mui/material";
import Tooltip from "@mui/material/Tooltip";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import LockIcon from "@mui/icons-material/Lock";
import LockOpenIcon from "@mui/icons-material/LockOpen";

// A reasonably comprehensive set of ISO currency codes companies actually report or
// trade in, plus GBX ("pence sterling" - a real EODHD trading-currency value for many
// LSE-listed stocks, not a typo). The currently detected/effective value is always
// added too (see buildOptions below), so an unusual already-set currency never
// disappears from the list just for not being "common".
const COMMON_CURRENCY_CODES = [
  "USD", "EUR", "GBP", "GBX", "JPY", "CNY", "CHF", "CAD", "AUD", "HKD", "SGD",
  "INR", "KRW", "BRL", "MXN", "ZAR", "SEK", "NOK", "DKK", "NZD", "TWD", "THB",
  "IDR", "MYR", "PHP", "VND", "TRY", "RUB", "PLN", "ILS", "AED", "SAR",
];

function buildOptions(...currentValues) {
  return Array.from(
    new Set([...COMMON_CURRENCY_CODES, ...currentValues.filter(Boolean)])
  );
}

/**
 * One currency field: a select, an info tooltip, and (only once the value differs
 * from the detected/auto-value) an inline panel offering to either revert the
 * session-only override or persist it to the database for every user.
 *
 * `locked`/`onUnlock` gate editing behind an extra step for fields that are rarely
 * wrong (trading currency) - omit them for fields that should always be directly
 * editable (reporting currency).
 */
function CurrencyCorrectionField({
  label,
  infoText,
  detectedValue,
  effectiveValue,
  onChangeOverride,
  onSaveToDatabase,
  locked = false,
}) {
  const [unlocked, setUnlocked] = useState(!locked);
  const [isSaving, setIsSaving] = useState(false);

  const hasPendingChange = Boolean(
    effectiveValue && detectedValue && effectiveValue !== detectedValue
  );

  const handleSelectChange = (e) => {
    const newValue = e.target.value;
    onChangeOverride(newValue === detectedValue ? null : newValue);
  };

  const handleRevert = () => {
    onChangeOverride(null);
    if (locked) setUnlocked(false);
  };

  const handleSave = () => {
    setIsSaving(true);
    onSaveToDatabase(effectiveValue).finally(() => {
      setIsSaving(false);
      if (locked) setUnlocked(false);
    });
  };

  return (
    <div style={{ minWidth: "220px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "4px", height: "20px" }}>
        <span style={{ fontSize: "0.8rem", color: "var(--border-input-fields)" }}>
          {label}
        </span>
        <Tooltip title={infoText} placement="top" arrow>
          <InfoOutlinedIcon style={{ fontSize: "16px", opacity: 0.7 }} />
        </Tooltip>
        {locked && (
          <Tooltip
            title={
              unlocked
                ? "Lock editing again"
                : "This is rarely wrong - unlock to edit anyway"
            }
            placement="top"
            arrow>
            {/* plain icon (not IconButton) so it's the same 16px height as the info
                icon above - IconButton's own touch-target padding was throwing off
                vertical alignment between this field and the one without a lock */}
            <span
              onClick={() => setUnlocked((prev) => !prev)}
              style={{
                display: "inline-flex",
                cursor: "pointer",
                opacity: 0.7,
              }}>
              {unlocked ? (
                <LockOpenIcon style={{ fontSize: "16px" }} />
              ) : (
                <LockIcon style={{ fontSize: "16px" }} />
              )}
            </span>
          </Tooltip>
        )}
      </div>
      <TextField
        select
        size="small"
        fullWidth
        value={effectiveValue || ""}
        disabled={!unlocked}
        onChange={handleSelectChange}
        sx={{
          "& .MuiInputBase-input.Mui-disabled": {
            WebkitTextFillColor: "var(--text-color-grey-scale)",
          },
        }}>
        {buildOptions(detectedValue, effectiveValue).map((code) => (
          <MenuItem key={code} value={code}>
            {code}
          </MenuItem>
        ))}
      </TextField>

      {hasPendingChange && (
        <div
          style={{
            marginTop: "8px",
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid var(--border-input-fields)",
            backgroundColor: "rgba(255, 165, 0, 0.08)",
          }}>
          <div style={{ fontSize: "0.85rem" }}>
            <strong>{label}:</strong>{" "}
            <span style={{ opacity: 0.6 }}>{detectedValue}</span>
            {" → "}
            <span style={{ color: "orange", fontWeight: 600 }}>
              {effectiveValue}
            </span>
          </div>
          <div style={{ fontSize: "0.75rem", opacity: 0.7, marginTop: "4px" }}>
            Saving updates the stored data for this stock - it will apply to
            every valuation, for every user, going forward.
          </div>
          <div
            style={{
              display: "flex",
              gap: "8px",
              justifyContent: "flex-end",
              marginTop: "8px",
            }}>
            <Button size="small" onClick={handleRevert} disabled={isSaving}>
              Revert
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="success"
              onClick={handleSave}
              disabled={isSaving}>
              {isSaving ? "Saving..." : "Save to database"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default CurrencyCorrectionField;
