import { AuthBindings, Authenticated, Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";

import {
  ErrorComponent,
  notificationProvider,
  RefineSnackbarProvider,
  ThemedLayoutV2,
  ThemedTitleV2,
} from "@refinedev/mui";

import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import routerBindings, {
  CatchAllNavigate,
  DocumentTitleHandler,
  NavigateToResource,
  UnsavedChangesNotifier,
} from "@refinedev/react-router-v6";
import dataProvider from "@refinedev/simple-rest";
import axios, { AxiosRequestConfig } from "axios";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import { Header } from "./components/header";
import { ColorModeContextProvider } from "./contexts/color-mode";
import { CredentialResponse } from "./interfaces/google";
import {
  BlogPostCreate,
  BlogPostEdit,
  BlogPostList,
  BlogPostShow,
} from "./examples/pages/blog-posts";
import {
  CategoryCreate,
  CategoryEdit,
  CategoryList,
  CategoryShow,
} from "./examples/pages/categories";
import { Login } from "./pages/login";
import { parseJwt } from "./utils/parse-jwt";
import { Geolocate } from "./sre-bot/pages/geolocate";
import { Incident } from "./sre-bot/pages/incident";
import { IncidentHistory } from "./sre-bot/pages/incident_history";
import { Webhooks } from "./sre-bot/pages/webhooks";
import { Faq } from "./sre-bot/pages/faq";
import { Dashboard } from "./sre-bot/pages/dashboard";

import * as Icons from "@mui/icons-material";

const axiosInstance = axios.create();
axiosInstance.interceptors.request.use((request: AxiosRequestConfig) => {
  const token = localStorage.getItem("token");
  if (request.headers) {
    request.headers["Authorization"] = `Bearer ${token}`;
  } else {
    request.headers = {
      Authorization: `Bearer ${token}`,
    };
  }

  return request;
});

function App() {
  const { t, i18n } = useTranslation();

  const authProvider: AuthBindings = {
    login: async ({ credential }: CredentialResponse) => {
      const profileObj = credential ? parseJwt(credential) : null;

      if (profileObj) {
        localStorage.setItem(
          "user",
          JSON.stringify({
            ...profileObj,
            avatar: profileObj.picture,
          })
        );

        localStorage.setItem("token", `${credential}`);

        return {
          success: true,
          redirectTo: "/",
        };
      }

      return {
        success: false,
      };
    },
    logout: async () => {
      const token = localStorage.getItem("token");

      if (token && typeof window !== "undefined") {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        axios.defaults.headers.common = {};
        window.google?.accounts.id.revoke(token, () => {
          return {};
        });
      }

      return {
        success: true,
        redirectTo: "/login",
      };
    },
    onError: async (error) => {
      console.error(error);
      return { error };
    },
    check: async () => {
      const token = localStorage.getItem("token");

      if (token) {
        return {
          authenticated: true,
        };
      }

      return {
        authenticated: false,
        error: {
          message: "Check failed",
          name: "Token not found",
        },
        logout: true,
        redirectTo: "/login",
      };
    },
    getPermissions: async () => null,
    getIdentity: async () => {
      const user = localStorage.getItem("user");
      if (user) {
        return JSON.parse(user);
      }

      return null;
    },
  };

  const i18nProvider = {
    translate: (key: string, params: object) => t(key, params),
    changeLocale: (lang: string) => i18n.changeLanguage(lang),
    getLocale: () => i18n.language,
  };

  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <ColorModeContextProvider>
          <CssBaseline />
          <GlobalStyles styles={{ html: { WebkitFontSmoothing: "auto" } }} />
          <RefineSnackbarProvider>
            <Refine
              dataProvider={dataProvider("https://api.fake-rest.refine.dev")}
              notificationProvider={notificationProvider}
              routerProvider={routerBindings}
              authProvider={authProvider}
              i18nProvider={i18nProvider}
              resources={[
                {
                  name: "SRE Bot",
                  meta: {
                    label: "SRE Bot",
                    icon: <Icons.Android />,
                  },
                },
                {
                  name: "Example Module",
                  meta: {
                    label: "Example Module",
                  },
                },
                {
                  name: "blog_posts",
                  list: "/blog-posts",
                  create: "/blog-posts/create",
                  edit: "/blog-posts/edit/:id",
                  show: "/blog-posts/show/:id",
                  meta: {
                    canDelete: true,
                    parent: "Example Module",
                  },
                },
                {
                  name: "categories",
                  list: "/categories",
                  create: "/categories/create",
                  edit: "/categories/edit/:id",
                  show: "/categories/show/:id",
                  meta: {
                    canDelete: true,
                    parent: "Example Module",
                  },
                },
                {
                  name: "Dashboard",
                  list: "/dashboard",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.HomeOutlined />,
                    label: "Dashboard",
                  },
                },
                {
                  name: "Start an Incident",
                  list: "/incident",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.AccessAlarms />,
                    label: "Start an Incident",
                  },
                },
                {
                  name: "Incident History",
                  list: "/incident_history",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.History />,
                    label: "Incident History",
                  },
                },
                {
                  name: "Webhooks",
                  list: "/webhooks",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.Webhook />,
                    label: "Webhooks",
                  },
                },
                {
                  name: "geolocate",
                  list: "/geolocate",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.LocationSearching />,
                    label: "Geolocate",
                  },
                },
                {
                  name: "FAQ",
                  list: "/faq",
                  meta: {
                    parent: "SRE Bot",
                    icon: <Icons.Info />,
                    label: "FAQ",
                  },
                },
              ]}
              options={{
                syncWithLocation: true,
                warnWhenUnsavedChanges: true,
                // projectId: "diNN0X-58019e-7Qd0eI",
              }}
            >
              <Routes>
                <Route
                  element={
                    <Authenticated fallback={<CatchAllNavigate to="/login" />}>
                      <ThemedLayoutV2
                        Header={() => <Header sticky />}
                        Title={({ collapsed }) => (
                          <ThemedTitleV2
                            collapsed={collapsed}
                            text="SRE Dev Portal"
                          />
                        )}
                      >
                        <Outlet />
                      </ThemedLayoutV2>
                    </Authenticated>
                  }
                >
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/incident" element={<Incident />} />
                  <Route
                    path="/incident_history"
                    element={<IncidentHistory />}
                  />
                  <Route path="/webhooks" element={<Webhooks />} />
                  <Route path="/geolocate" element={<Geolocate />} />
                  <Route path="/faq" element={<Faq />} />
                  <Route
                    index
                    element={<NavigateToResource resource="blog_posts" />}
                  />
                  <Route path="/blog-posts">
                    <Route index element={<BlogPostList />} />
                    <Route path="create" element={<BlogPostCreate />} />
                    <Route path="edit/:id" element={<BlogPostEdit />} />
                    <Route path="show/:id" element={<BlogPostShow />} />
                  </Route>
                  <Route path="/categories">
                    <Route index element={<CategoryList />} />
                    <Route path="create" element={<CategoryCreate />} />
                    <Route path="edit/:id" element={<CategoryEdit />} />
                    <Route path="show/:id" element={<CategoryShow />} />
                  </Route>
                  <Route path="*" element={<ErrorComponent />} />
                </Route>
                <Route
                  element={
                    <Authenticated fallback={<Outlet />}>
                      <NavigateToResource />
                    </Authenticated>
                  }
                >
                  <Route path="/login" element={<Login />} />
                </Route>
              </Routes>

              <RefineKbar />
              <UnsavedChangesNotifier />
              <DocumentTitleHandler />
            </Refine>
          </RefineSnackbarProvider>
        </ColorModeContextProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}

export default App;
