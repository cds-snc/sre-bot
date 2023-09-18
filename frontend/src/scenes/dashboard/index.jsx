import Header from "../../components/Header";
import { Box } from "@mui/material";


// Return dashboard component. Right now it just displays the title and subtitle.
const Dashboard = () => {
    return (
              <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="Dashboard" subtitle="Welcome to the dashboard (ie home page)." />
                </Box>
            </Box>
    );
 }
export default Dashboard;