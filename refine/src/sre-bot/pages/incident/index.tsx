import { Box, Typography } from "@mui/material";

// Return a Incident component. Right now it just displays the title and subtitle.
export const Incident: React.FC = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h2" align="center" color="textPrimary">
          Incident
        </Typography>
        <Typography variant="h3" align="center" color="textPrimary">
          Start a new incident here.
        </Typography>
      </Box>
    </Box>
  );
};
