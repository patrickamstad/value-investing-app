import React, { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Box, Typography } from "@mui/material";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import { v4 as uuidv4 } from "uuid";

export const ACCEPTED_FILE_TYPES = {
  "application/pdf": [".pdf"],
};

function DropZone({ onFilesAdded }) {
  const [rejectedNames, setRejectedNames] = useState([]);

  const onDrop = async (acceptedFiles, rejectedFiles) => {
    setRejectedNames(rejectedFiles.map((r) => r.file.name));

    if (acceptedFiles.length === 0) return;

    const prepared = await Promise.all(
      acceptedFiles.map(async (file) => ({
        id: uuidv4(),
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
        data: await file.arrayBuffer(),
      }))
    );

    onFilesAdded(prepared);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    multiple: true,
  });

  return (
    <Box>
      <Box
        {...getRootProps()}
        sx={{
          border: isDragActive
            ? "2px dashed var(--action-color)"
            : "2px dashed var(--border-input-fields)",
          backgroundColor: isDragActive
            ? "var(--action-color-more-transparent)"
            : "var(--background-glass-card)",
          padding: "48px 24px",
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color 0.2s, background-color 0.2s",
        }}>
        <input {...getInputProps()} />
        <UploadFileOutlinedIcon
          sx={{
            fontSize: 48,
            color: isDragActive ? "var(--action-color)" : "var(--text-color-grey-scale)",
            mb: 1,
          }}
        />
        <Typography sx={{ color: "var(--header-color)", fontWeight: 600, mb: 0.5 }}>
          {isDragActive ? "Drop files here" : "Drag & drop files here"}
        </Typography>
        <Typography sx={{ color: "var(--text-color-grey-scale)", fontSize: "0.85rem" }}>
          or click to browse — PDF files only
        </Typography>
      </Box>

      {rejectedNames.length > 0 && (
        <Typography sx={{ color: "var(--error-red)", fontSize: "0.8rem", mt: 1 }}>
          Rejected (unsupported format):{" "}
          {rejectedNames.join(", ")}
        </Typography>
      )}
    </Box>
  );
}

export default DropZone;
