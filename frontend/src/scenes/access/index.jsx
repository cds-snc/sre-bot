import Header from "../../components/Header";
import { Box } from "@mui/material";


// Return AWS Access component. Right now it just displays the title and subtitle.
const AWS_Access= () => {
    return (
              <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="AWS Access" subtitle="Request/View/Grant AWS Production access"/>
                </Box>
            </Box>
    );
 }
export default AWS_Access;