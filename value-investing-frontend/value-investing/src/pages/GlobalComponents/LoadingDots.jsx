import React from "react";
import { Box } from "@mui/material";

function LoadingDots({ size = 6, color = "var(--action-color)", gap = 4 }) {
  return (
    <Box
      sx={{
        "@keyframes blink": {
          "0%, 80%, 100%": { opacity: 0 },
          "40%": { opacity: 1 },
        },
        display: "flex",
        alignItems: "center",
        gap: `${gap}px`,
        "& span": {
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: color,
          animation: "blink 1.4s infinite ease-in-out",
        },
        "& span:nth-of-type(1)": { animationDelay: "0s" },
        "& span:nth-of-type(2)": { animationDelay: "0.2s" },
        "& span:nth-of-type(3)": { animationDelay: "0.4s" },
      }}>
      <span /><span /><span />
    </Box>
  );
}

export default LoadingDots;
