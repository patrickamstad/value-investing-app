import React, { useState, useEffect, useRef, useCallback } from "react";
import { Box, Button, Typography, CircularProgress, Tooltip, Chip, Divider, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, DialogContentText,
} from "@mui/material";
import { useSelector } from "react-redux";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import DropZone from "./DropZone";
import StagedFilesList from "./StagedFilesList";
import UploadedFilesList from "./UploadedFilesList";
import LoadingDots from "../../../GlobalComponents/LoadingDots";
import { loadStagedFiles, saveStagedFiles } from "./fileStorageService";
import axiosInstance from "../../../../axios/axiosConfig";
import { useSnackbar } from "../../../GlobalComponents/SnackbarProvider";

function AnalystReport() {
  const [stagedFiles, setStagedFiles] = useState([]);
  const [documentTypes, setDocumentTypes] = useState({});
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [duplicateNames, setDuplicateNames] = useState([]);
  const [processing, setProcessing] = useState(false);

  const [reports, setReports]                   = useState([]);
  const [currentReportPk, setCurrentReportPk]   = useState(null);
  const [showWarningModal, setShowWarningModal]  = useState(false);
  const [generatingReport, setGeneratingReport]  = useState(false);
  const reportPollRef = useRef(null);

  const { showMessage } = useSnackbar();
  const analysisState = useSelector((state) => state.analysis);
  const qfs_symbol = analysisState?.selectedTickerSymbol?.qfs_symbol;

  const currentReport = reports.find((r) => r.id === currentReportPk) ?? null;
  const currentStatus = currentReport?.status ?? null;

  const fetchUploadedFiles = useCallback(async () => {
    if (!qfs_symbol) return;
    try {
      const { data } = await axiosInstance.get(`/analyst-reports/${qfs_symbol}/`);
      setUploadedFiles(data);
    } catch {
      showMessage("Failed to load uploaded files.", "error");
    }
  }, [qfs_symbol]);

  useEffect(() => {
    loadStagedFiles().then(setStagedFiles);
  }, []);

  useEffect(() => {
    fetchUploadedFiles();
  }, [fetchUploadedFiles]);

  useEffect(() => {
    const shouldPoll = uploadedFiles.some((f) => ["uploaded", "scanning", "extracting"].includes(f.status));
    if (!shouldPoll) return;

    const interval = setInterval(fetchUploadedFiles, 3000);
    return () => clearInterval(interval);
  }, [uploadedFiles, fetchUploadedFiles]);

  // Load all reports for this symbol on mount
  useEffect(() => {
    if (!qfs_symbol) return;
    axiosInstance.get(`/analyst-reports/${qfs_symbol}/reports/`)
      .then(({ data }) => {
        setReports(data);
        const latest = data[0] ?? null;
        if (latest) setCurrentReportPk(latest.id);
      })
      .catch(() => {});
  }, [qfs_symbol]);

  const fetchReportStatus = useCallback(async () => {
    if (!currentReportPk) return;
    try {
      const { data } = await axiosInstance.get(`/analyst-reports/reports/${currentReportPk}/`);
      setReports((prev) => prev.map((r) => r.id === currentReportPk ? data : r));
    } catch {}
  }, [currentReportPk]);

  // Only poll while the current report is actively in-flight
  useEffect(() => {
    if (!currentReportPk) return;
    if (currentStatus !== "pending" && currentStatus !== "generating") return;

    reportPollRef.current = setInterval(fetchReportStatus, 4000);
    return () => clearInterval(reportPollRef.current);
  }, [currentStatus, currentReportPk, fetchReportStatus]);

  const handleFilesAdded = async (newFiles) => {
    const existingNames = new Set(stagedFiles.map((f) => f.name));
    const accepted = newFiles.filter((f) => !existingNames.has(f.name));
    const duplicates = newFiles.filter((f) => existingNames.has(f.name)).map((f) => f.name);

    setDuplicateNames(duplicates);

    if (duplicates.length > 0) {
      showMessage(`Already staged (skipped): ${duplicates.join(", ")}`, "warning");
    }

    if (accepted.length === 0) return;

    const updated = [...stagedFiles, ...accepted];
    setStagedFiles(updated);
    await saveStagedFiles(updated);
  };

  const handleRemove = async (id) => {
    const updated = stagedFiles.filter((f) => f.id !== id);
    setStagedFiles(updated);
    await saveStagedFiles(updated);
    setDocumentTypes((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const handleTypeChange = (id, value) => {
    setDocumentTypes((prev) => ({ ...prev, [id]: value }));
  };

  const handleRetry = async (uploadId) => {
    try {
      await axiosInstance.post(`/analyst-reports/retry/${uploadId}/`);
      await fetchUploadedFiles();
    } catch (err) {
      showMessage(err.response?.data?.error || "Retry failed.", "error");
    }
  };

  const handleDeleteUpload = async (uploadId) => {
    try {
      await axiosInstance.delete(`/analyst-reports/uploads/${uploadId}/`);
      setUploadedFiles((prev) => prev.filter((f) => f.id !== uploadId));
      showMessage("File deleted successfully.", "success");
    } catch (err) {
      showMessage(err.response?.data?.detail || "Delete failed.", "error");
    }
  };

  const handleUpdateDocumentType = async (uploadId, newType) => {
    try {
      const { data } = await axiosInstance.patch(
        `/analyst-reports/uploads/${uploadId}/document-type/`,
        { document_type: newType }
      );
      setUploadedFiles((prev) => prev.map((f) => (f.id === uploadId ? data : f)));
    } catch (err) {
      showMessage(err.response?.data?.error || "Failed to update document type.", "error");
    }
  };

  const triggerReportGeneration = async () => {
    setShowWarningModal(false);
    setGeneratingReport(true);
    try {
      const { data } = await axiosInstance.post(`/analyst-reports/${qfs_symbol}/generate/`);
      // Prepend the new pending report to the list and start polling it
      setReports((prev) => [{ id: data.report_id, status: "pending", created_at: new Date().toISOString(), presigned_url: null }, ...prev]);
      setCurrentReportPk(data.report_id);
    } catch (err) {
      showMessage(err.response?.data?.error || "Failed to start report generation.", "error");
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleCreateReport = () => {
    const hasProcessing = uploadedFiles.some((f) =>
      ["uploaded", "scanning", "extracting"].includes(f.status)
    );
    if (hasProcessing) {
      setShowWarningModal(true);
    } else {
      triggerReportGeneration();
    }
  };

  const handleProcessFiles = async () => {
    setProcessing(true);
    try {
      for (const file of stagedFiles) {
        // 1. Get presigned PUT URL from backend
        const { data: { presigned_url, s3_key } } = await axiosInstance.post(
          "/analyst-reports/presigned-url/",
          { qfs_symbol, file_name: file.name, file_type: file.type }
        );

        // 2. Upload file bytes directly to S3 — plain fetch, no auth header
        const blob = new Blob([file.data], { type: file.type });
        const s3Response = await fetch(presigned_url, {
          method: "PUT",
          body: blob,
          headers: { "Content-Type": file.type },
        });

        if (!s3Response.ok) {
          throw new Error(`S3 upload failed for ${file.name}: ${s3Response.statusText}`);
        }

        // 3. Confirm upload to backend so DB record is created
        await axiosInstance.post("/analyst-reports/confirm/", {
          qfs_symbol,
          s3_key,
          file_name: file.name,
          file_type: file.type,
          document_type: documentTypes[file.id] && documentTypes[file.id] !== "auto" ? documentTypes[file.id] : null,
        });
      }

      // 4. Clear staged files and refresh the uploaded list
      await saveStagedFiles([]);
      setStagedFiles([]);
      setDocumentTypes({});
      setDuplicateNames([]);
      await fetchUploadedFiles();
      showMessage("Files uploaded successfully.", "success");
    } catch (err) {
      showMessage(err.message || "Upload failed. Please try again.", "error");
    } finally {
      setProcessing(false);
    }
  };

  const noDoneFiles = uploadedFiles.filter((f) => f.status === "done").length === 0;
  const disabledReason =
    currentStatus === "pending"    ? "A report is already queued." :
    currentStatus === "generating" ? "A report is already being generated." :
    generatingReport               ? "Starting report generation…" :
    noDoneFiles                    ? "Upload and process at least one file first." :
    null;

  return (
    <Box sx={{ mt: 4 }}>

      {/* Card 1: Generated Reports */}
      <div className="glass-card" style={{ marginTop: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
          <div className="title-mid-size">Generated Reports</div>
          <Tooltip title={disabledReason ?? ""} arrow disableHoverListener={!disabledReason}>
            <span>
              <Button
                variant="contained"
                className="contained-custom-button"
                startIcon={<AssessmentOutlinedIcon className="button-icon" />}
                disabled={!!disabledReason}
                onClick={handleCreateReport}>
                Create Analyst Report
              </Button>
            </span>
          </Tooltip>
        </div>

        {reports.length === 0 ? (
          <Typography sx={{ color: "var(--text-color-grey-scale)", fontSize: "0.85rem" }}>
            No reports generated yet.
          </Typography>
        ) : (
          reports.map((r, index) => (
            <React.Fragment key={r.id}>
              <Box sx={{ display: "flex", alignItems: "center", py: 1, gap: 1 }}>
                <ArticleOutlinedIcon sx={{ color: "var(--text-color-grey-scale)", flexShrink: 0 }} />
                <Typography sx={{ color: "var(--header-color)", fontSize: "0.9rem", flex: 1 }}>
                  Analyst Report {qfs_symbol} 
                     <span
                                className="title-last-close-price"
                                style={{ fontSize: "11px", marginLeft: "12px" }}>
                                ({new Date(r.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })})
                              </span>
                  
                   {/* &mdash; Created at {new Date(r.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })} */}
                </Typography>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  {(r.status === "pending" || r.status === "generating") && (
                    <>
                      <LoadingDots />
                      <Chip
                        label={r.status === "pending" ? "Queued" : "Generating..."}
                        size="small"
                        variant="outlined"
                        sx={{
                          color: "var(--action-color)",
                          borderColor: "var(--action-color)",
                          backgroundColor: "transparent",
                          fontFamily: "var(--font-family)",
                          fontSize: "0.7rem",
                          borderRadius: "var(--var-border-radius)",
                        }}
                      />
                    </>
                  )}
                  {r.status === "failed" && (
                    <Chip
                      label="Failed"
                      size="small"
                      variant="outlined"
                      sx={{
                        color: "var(--error-red)",
                        borderColor: "var(--error-red)",
                        backgroundColor: "transparent",
                        fontFamily: "var(--font-family)",
                        fontSize: "0.7rem",
                        borderRadius: "var(--var-border-radius)",
                      }}
                    />
                  )}
                  {r.status === "done" && r.presigned_url && (
                    <Tooltip title="Download report" arrow>
                      <IconButton
                        component="a"
                        href={r.presigned_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        size="small"
                        sx={{ color: "var(--action-color)" }}>
                        <FileDownloadOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              </Box>
              {index < reports.length - 1 && (
                <Divider sx={{ borderColor: "var(--border-glass-card)" }} />
              )}
            </React.Fragment>
          ))
        )}
      </div>

      {/* Card 2: Documents (upload + processed files) */}
      <div className="glass-card" style={{ marginTop: "24px" }}>
        <div className="title-mid-size" style={{ marginBottom: "20px" }}>Documents</div>



        <DropZone onFilesAdded={handleFilesAdded} />



        <StagedFilesList
          files={stagedFiles}
          onRemove={handleRemove}
          documentTypes={documentTypes}
          onTypeChange={handleTypeChange}
        />

        <Box sx={{ mt: "12px", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 2 }}>
          <Button
            variant="contained"
            disabled={stagedFiles.length === 0 || processing}
            className="contained-custom-button"
            onClick={handleProcessFiles}>
            {processing ? "Uploading..." : "Process Files"}
          </Button>
          {processing && <CircularProgress className="custom-circular-progress" />}
        </Box>

        <UploadedFilesList
          files={uploadedFiles}
          onRetry={handleRetry}
          onDelete={handleDeleteUpload}
          onTypeUpdate={handleUpdateDocumentType}
          reportInFlight={currentStatus === "pending" || currentStatus === "generating"}
        />
      </div>

      {/* Warning modal — some files still processing */}
      <Dialog open={showWarningModal} onClose={() => setShowWarningModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Some files are still processing</DialogTitle>
        <DialogContent>
          <DialogContentText>These files haven't finished yet and won't be included in the report:</DialogContentText>
          <Box component="ul" sx={{ mt: 1 }}>
            {uploadedFiles
              .filter((f) => ["uploaded", "scanning", "extracting"].includes(f.status))
              .map((f) => <li key={f.id}><Typography variant="body2">{f.file_name}</Typography></li>)
            }
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowWarningModal(false)}>Cancel</Button>
          <Button variant="contained" onClick={triggerReportGeneration}>Generate Anyway</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default AnalystReport;
