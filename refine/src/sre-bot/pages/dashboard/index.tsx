import { Box, Typography } from "@mui/material";

// Return dashboard component. Right now it just displays the title and subtitle.
export const Dashboard: React.FC = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h2" align="center" color="textPrimary">
          Dashboard
        </Typography>
      </Box>
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="subtitle1" align="center" color="textPrimary">
          Welcome to the dashboard (ie home page).
        </Typography>
      </Box>
    </Box>
  );
};
