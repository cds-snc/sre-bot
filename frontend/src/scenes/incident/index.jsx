import { Box } from "@mui/material";
import Header from "../../components/Header";


// Return a Incident component. Right now it just displays the title and subtitle.
const Incident= () => {
  return (
    <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="Incident" subtitle="Start a new incident here."/>
                </Box>
            </Box>
)};

export default Incident;