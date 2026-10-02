import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import IconButton from "@mui/material/IconButton";
import Avatar from "@mui/material/Avatar";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Typography from "@mui/material/Typography";
import WbSunnyOutlinedIcon from "@mui/icons-material/WbSunnyOutlined";
import NightlightOutlinedIcon from "@mui/icons-material/NightlightOutlined";

// User settings menu options
const settings = ["Profile", "Account", "Dashboard", "Logout"];

const Sidebar = ({ mobileOpen, handleDrawerToggle, window }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname;

  // --- Account Info & Theme State (Ported from NavBar) ---
  const [anchorElUser, setAnchorElUser] = useState(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "light";
  });

  const handleOpenUserMenu = (event) => {
    setAnchorElUser(event.currentTarget);
  };

  const handleCloseUserMenu = () => {
    setAnchorElUser(null);
  };

  useEffect(() => {
    document.body.classList.toggle("light-theme", theme === "light");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const handleThemeToggle = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };
  // ------------------------------------------------------

  const menuItems = [
    { text: "Screener", path: "/screener" },
    // { text: "Valuation", path: "/valuation" },
    { text: "Analysis", path: "/analysis" },
    { text: "Watchlists", path: "/watchlist" },
    // { text: "Testing", path: "/testing" },
  ];

  const drawerContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Logo Section */}
      <div
        style={{
          padding: "24px",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.12)",
        }}>
        <div>
          <h1
            style={{
              margin: 0,
              color: "var(--header-color)",
              fontWeight: "bold",
              fontSize: "1.125rem",
              fontFamily: "var(--font-family)",
            }}>
            A&F
          </h1>
          <span
            style={{
              color: "var(--text-color-grey-scale)",
              fontSize: "0.75rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}>
            StockVal v1.0
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <List
        sx={{ flex: 1, padding: "24px 0" }}
        className="custom-list-transparent">
        {menuItems.map((item) => {
          const isActive = currentPath === item.path;
          return (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                onClick={() => {
                  navigate(item.path);
                  if (mobileOpen) handleDrawerToggle();
                }}
                sx={{
                  padding: "12px 24px",
                  transition: "all 0.2s ease",
                  borderLeft: isActive
                    ? "3px solid var(--action-color)"
                    : "3px solid transparent",
                  backgroundColor: isActive
                    ? "var(--action-color-more-transparent)"
                    : "transparent",
                  color: isActive
                    ? "var(--action-color)"
                    : "var(--text-color-grey-scale)",
                  "&:hover": {
                    backgroundColor: "var(--input-fields-hover-bg-color)",
                    color: "var(--action-color)",
                  },
                }}>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    style: {
                      fontWeight: isActive ? 600 : 500,
                      fontFamily: "var(--font-family)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      fontSize: "0.875rem",
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      {/* Footer: Account Info & Settings */}
      <div
        style={{
          padding: "16px",
          borderTop: "1px solid rgba(255, 255, 255, 0.12)",
          backgroundColor: "rgba(0,0,0,0.02)", // Subtle contrast for footer
        }}>
        {/* Controls Row: Theme & Avatar */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            mb: 2,
            px: 1,
          }}>
          {/* Theme Toggle */}
          <IconButton
            onClick={handleThemeToggle}
            sx={{ color: "var(--text-color-grey-scale)" }}>
            {theme === "light" ? (
              <NightlightOutlinedIcon fontSize="small" />
            ) : (
              <WbSunnyOutlinedIcon fontSize="small" />
            )}
          </IconButton>

          {/* User Avatar */}
          <Box>
            <IconButton onClick={handleOpenUserMenu} sx={{ p: 0 }}>
              <Avatar
                alt="User Avatar"
                src="/static/images/avatar/2.jpg"
                sx={{
                  width: 32,
                  height: 32,
                  border: "1px solid rgba(255,255,255,0.2)",
                }}
              />
            </IconButton>
            <Menu
              sx={{ mt: "-45px", ml: "45px" }} // Opens to the right/top of sidebar
              id="menu-appbar"
              anchorEl={anchorElUser}
              anchorOrigin={{ vertical: "top", horizontal: "right" }}
              keepMounted
              transformOrigin={{ vertical: "bottom", horizontal: "left" }}
              open={Boolean(anchorElUser)}
              onClose={handleCloseUserMenu}>
              {settings.map((setting) => (
                <MenuItem key={setting} onClick={handleCloseUserMenu}>
                  <Typography textAlign="center">{setting}</Typography>
                </MenuItem>
              ))}
            </Menu>
          </Box>
        </Box>

        {/* Sign Out Button */}
        <List disablePadding>
          <ListItem disablePadding>
            <ListItemButton
              onClick={() => navigate("/")}
              sx={{
                padding: "10px 16px",
                borderRadius: "8px",
                transition: "all 0.2s ease",
                color: "var(--text-color-grey-scale)",
                "&:hover": {
                  backgroundColor: "rgba(255, 82, 82, 0.1)", // Subtle red tint on hover
                  color: "#ff5252",
                },
              }}>
              <ListItemText
                primary="Sign Out"
                primaryTypographyProps={{
                  style: {
                    fontWeight: 500,
                    fontFamily: "var(--font-family)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    fontSize: "0.75rem",
                    textAlign: "center",
                  },
                }}
              />
            </ListItemButton>
          </ListItem>
        </List>
      </div>
    </div>
  );

  const container =
    window !== undefined ? () => window().document.body : undefined;

  // Drawer Styles
  const drawerPaperStyles = {
    boxSizing: "border-box",
    width: "var(--drawer-width)",
    borderRight: "1px solid rgba(255, 255, 255, 0.12)",
    backgroundColor: "var(--background-color-nav-bar)",
    color: "var(--header-color)",
    fontFamily: "var(--font-family)",
  };

  return (
    <Box
      component="nav"
      sx={{ width: { md: "var(--drawer-width)" }, flexShrink: { md: 0 } }}>
      {/* Mobile Drawer */}
      <Drawer
        container={container}
        variant="temporary"
        open={mobileOpen}
        onClose={handleDrawerToggle}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": drawerPaperStyles,
        }}>
        {drawerContent}
      </Drawer>

      {/* Desktop Drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", md: "block" },
          "& .MuiDrawer-paper": drawerPaperStyles,
        }}
        open>
        {drawerContent}
      </Drawer>
    </Box>
  );
};

export default Sidebar;
