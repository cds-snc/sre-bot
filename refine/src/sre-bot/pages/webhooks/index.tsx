import { Box, Typography } from "@mui/material";

// Setup the webhooks component. Right now it just displays the title and subtitle.
export const Webhooks: React.FC = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h2" align="center" color="textPrimary">
          Webhooks
        </Typography>
        <Typography variant="h3" align="center" color="textPrimary">
          Manage all webhooks here.
        </Typography>
      </Box>
    </Box>
  );
};
