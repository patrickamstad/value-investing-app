import React from "react";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import PhoneIcon from "@mui/icons-material/Phone";
import FavoriteIcon from "@mui/icons-material/Favorite";
import PersonPinIcon from "@mui/icons-material/PersonPin";
import PhoneMissedIcon from "@mui/icons-material/PhoneMissed";
import FeedOutlinedIcon from "@mui/icons-material/FeedOutlined";
import ShowChartOutlinedIcon from "@mui/icons-material/ShowChartOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";

function AnalysisTabs({ tab, setTab }) {
  const handleChange = (e, newValue) => {
    setTab(newValue);
  };

  return (
    <Tabs
      style={{ marginTop: "32px" }}
      value={tab}
      onChange={handleChange}
      aria-label="icon position tabs example">
      <Tab icon={<FeedOutlinedIcon />} iconPosition="start" label="Overview" />
      <Tab
        icon={<ShowChartOutlinedIcon />}
        iconPosition="start"
        label="Valuation"
      />
      <Tab
        icon={<AssessmentOutlinedIcon />}
        iconPosition="start"
        label="Analyst Report"
      />
      {/* <Tab icon={<FavoriteIcon />} iconPosition="start" label="end" />
      <Tab icon={<PersonPinIcon />} iconPosition="start" label="end" /> */}
    </Tabs>
  );
}

export default AnalysisTabs;
