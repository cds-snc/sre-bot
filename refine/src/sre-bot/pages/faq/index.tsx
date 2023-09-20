import { Box, Typography } from "@mui/material";
// import Header from "../../components/Header";

export const Faq: React.FC = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h2" align="center" color="textPrimary">
          FAQ
        </Typography>
      </Box>
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="subtitle1" align="center" color="textPrimary">
          Frequently Asked Questions section.
        </Typography>
      </Box>
    </Box>
  );
};
