import { Box, Typography } from "@mui/material";

export const IncidentHistory: React.FC = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h2" align="center" color="textPrimary">
          Incident History
        </Typography>
        <Typography variant="h3" align="center" color="textPrimary">
          Listing of all historical incidents
        </Typography>
      </Box>
    </Box>
  );
};
