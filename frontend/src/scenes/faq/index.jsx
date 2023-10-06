import { Box, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography } from "@mui/material";
import { Book } from "@mui/icons-material";
import Header from "../../components/Header";

const Faq = () => {
  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="FAQ" subtitle="Frequently Asked Questions section." />
      </Box>
      <Box> 
       <Typography variant="h3">Incident Management</Typography>
        <List>
          <ListItemButton component="a" href="https://articles.alpha.canada.ca/cds-intranet-employee-guide/incident-management-handbook/incident-response-runbook/" target="_blank" rel="noopener noreferrer">
            <ListItemIcon>
              <Book />
            </ListItemIcon>
            <ListItemText primaryTypographyProps={{ variant: "h4" }} primary="Incident Response Runbook" />
          </ListItemButton>
          <ListItemButton component="a" href="https://articles.alpha.canada.ca/cds-intranet-employee-guide/incident-management-handbook/" target="_blank" rel="noopener noreferrer" >
            <ListItemIcon>
              <Book />
            </ListItemIcon>
            <ListItemText primaryTypographyProps={{ variant: "h4" }} primary="Incident Management Handbook" />
          </ListItemButton>
        </List>
      </Box>
    </Box>
  );
};

export default Faq;