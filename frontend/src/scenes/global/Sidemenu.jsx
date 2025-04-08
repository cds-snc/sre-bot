import React, { useEffect, useState } from 'react';
import { ProSidebar, Menu, MenuItem } from "react-pro-sidebar";
import "react-pro-sidebar/dist/css/styles.css";
import { Box, IconButton, useTheme, Typography } from "@mui/material";
import { Link } from "react-router-dom";
import { tokens } from "../../theme";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";
import AccessAlarmsIcon from '@mui/icons-material/AccessAlarms';
import HistoryIcon from '@mui/icons-material/History';
import WebhookIcon from '@mui/icons-material/Webhook';
import KeyIcon from '@mui/icons-material/Key';
import NewReleasesIcon from '@mui/icons-material/NewReleases';
import LocationSearchingIcon from '@mui/icons-material/LocationSearching';
import InfoIcon from '@mui/icons-material/Info';
import LogoutIcon from '@mui/icons-material/Logout';

// Menu item component
const Item = ({ title, to, icon, selected, setSelected }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <MenuItem
      active={selected === title}
      style={{
        color: colors.grey[100],
      }}
      onClick={() => setSelected(title)}
      icon={icon}
    >
      <Typography variant="h5" >{title}</Typography>
      <Link to={to} />
    </MenuItem>
  );
};

// Sidemenu component to display the Sidemenu in a scene
const Sidemenu = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selected, setSelected] = useState("Dashboard");

  // Get the user data to see who is the logged in user
  const useUserData = () => {
    const [userData, setUserData] = useState(null);

    useEffect(() => {
      // Make a GET request to the "/user" endpoint
      fetch('/user')
        .then(response => {
          // Check if the response status code is OK (200)
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          // Parse the JSON response
          return response.json();
        })
        .then(data => {
          // Handle the JSON data from the response
          setUserData(data);
        })
        .catch(error => {
          console.error('There was a problem with the fetch operation:', error);
        });
    }, []);

    return userData;
  };

  // call the useUserData function to get the user data
  const userData = useUserData();

  return (
    // setup the links behaviour and colors
    <Box
      sx={{
        "& .pro-sidebar-inner": {
          background: `${colors.primary[400]} !important`,
        },
        "& .pro-icon-wrapper": {
          backgroundColor: "transparent !important",
        },
        "& .pro-inner-item": {
          padding: "10px 35px 5px 20px !important",
        },
        "& .pro-inner-item:hover": {
          color: "#5398FE !important",
        },
        "& .pro-menu-item.active": {
          color: "#0074d8 !important",
        },
      }}
    >
      <ProSidebar collapsed={isCollapsed}>
        <Menu iconShape="square">
          {/* Set the up the logo and Menu items. In particular, flush out the behaviour of the Menu when it is collapsed or expanded.  */}
          <MenuItem
            onClick={() => setIsCollapsed(!isCollapsed)}
            icon={isCollapsed ? <MenuOutlinedIcon /> : undefined}
            style={{
              margin: "10px 0 20px 0",
              color: colors.grey[100],
            }}
          >
            {!isCollapsed && (
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="center"
                ml="15px"
              >
                <Typography variant="h3" color={colors.grey[100]}>
                  SRE Bot
                </Typography>
                <IconButton onClick={() => setIsCollapsed(!isCollapsed)}>
                  <MenuOutlinedIcon />
                </IconButton>
              </Box>
            )}
          </MenuItem>

          {/* If the menu is not collapsed, setup the logo and first name of the logged in user */}
          {!isCollapsed && (
            <Box mb="25px">
              <Box display="flex" justifyContent="center" alignItems="center">
                <img
                  alt="sre-bot-user"
                  width="100px"
                  height="100px"
                  src={`../../static/sre_bot_logo.png`}
                  style={{ cursor: "pointer", borderRadius: "50%" }}
                />
              </Box>
              <Box textAlign="center">
                <Typography
                  variant="h4"
                  color={colors.grey[100]}
                  fontWeight="bold"
                  sx={{ m: "10px 0 0 0" }}
                >
                  Hello {userData && userData.name}!
                </Typography>
              </Box>
            </Box>
          )}

          {/* Setup the menu items and the links to the different pages. */}
          <Box paddingLeft={isCollapsed ? undefined : "10%"}>
            <Item
              title="Dashboard"
              to="/"
              icon={<HomeOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="AWS Access"
              to="/access"
              icon={<KeyIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Start an Incident"
              to="/incident"
              icon={<AccessAlarmsIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Incident History"
              to="/incident_history"
              icon={<HistoryIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Manage Webhooks"
              to="/webhooks"
              icon={<WebhookIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Geolocate an IP"
              to="/geolocate"
              icon={<LocationSearchingIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="FAQ Page"
              to="/faq"
              icon={<InfoIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Version"
              to="/version"
              icon={<NewReleasesIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Logout"
              to="/logout"
              icon={<LogoutIcon />}
              selected={selected}
              setSelected={setSelected}
            />
          </Box>
        </Menu>
      </ProSidebar>
    </Box>
  );
};

export default Sidemenu;