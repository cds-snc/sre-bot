import React from "react";
import dompurify from "dompurify";
import logo from "../../assets/sre_bot_logo.svg";

export const AppIcon: React.FC = () => {
  const sanitizedLogo = dompurify.sanitize(logo);
  return <img src={sanitizedLogo} />;
};
