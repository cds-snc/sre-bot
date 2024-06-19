import Header from "../../components/Header";
import { Box } from "@mui/material";
import * as React from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Typography from '@mui/material/Typography';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import FiberNewIcon from '@mui/icons-material/FiberNew';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import ManageHistoryIcon from '@mui/icons-material/ManageHistory';

const AWS_Access= () => {
    return (
    <Box m="20px">
         <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="AWS Access" />
                </Box>
      <div>
        <Accordion>
          <AccordionSummary
            expandIcon={<ArrowDownwardIcon />}
            aria-controls="panel1-content"
            id="panel1-header"
          >
            <Box display="flex" alignItems="center">
                <FiberNewIcon sx={{ mr: 1 }} />
                <Typography variant="h4">Request AWS Production Access</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
             Request Access to an AWS account. The SRE team will be notified and the request will then be approved or denied.
            </Typography>
          </AccordionDetails>
        </Accordion>
        <Accordion>
          <AccordionSummary
            expandIcon={<ArrowDropDownIcon />}
            aria-controls="panel2-content"
            id="panel2-header"
          >
             <Box display="flex" alignItems="center">
                <LibraryBooksIcon sx={{ mr: 1 }} />
                <Typography variant="h4">View Outstanding AWS Access Requests</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              View current requests that have not been approved or denied.
            </Typography>
          </AccordionDetails>
        </Accordion>
        <Accordion>
          <AccordionSummary
            expandIcon={<ArrowDropDownIcon />}
            aria-controls="panel3-content"
            id="panel3-header"
          >
        <Box display="flex" alignItems="center">
            <ManageHistoryIcon sx={{ mr: 1 }} />
            <Typography variant="h4">View Past AWS Access Requests</Typography>
        </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              View all past approved/denied requests.
            </Typography>
          </AccordionDetails>
        </Accordion>
      </div>
      </Box>
    );
  }
export default AWS_Access;