import { Edit } from "@refinedev/mui";
import { Box, TextField } from "@mui/material";
import { useForm } from "@refinedev/react-hook-form";
import { IResourceComponentsProps, useTranslate } from "@refinedev/core";

export const CategoryEdit: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const {
    saveButtonProps,
    refineCore: { queryResult },
    register,
    control,
    formState: { errors },
  } = useForm();

  const categoriesData = queryResult?.data?.data;

  return (
    <Edit saveButtonProps={saveButtonProps}>
      <Box
        component="form"
        sx={{ display: "flex", flexDirection: "column" }}
        autoComplete="off"
      >
        <TextField
          {...register("id", {
            required: "This field is required",
            valueAsNumber: true,
          })}
          error={!!(errors as any)?.id}
          helperText={(errors as any)?.id?.message}
          margin="normal"
          fullWidth
          InputLabelProps={{ shrink: true }}
          type="number"
          label={translate("categories.fields.id")}
          name="id"
          disabled
        />
        <TextField
          {...register("title", {
            required: "This field is required",
          })}
          error={!!(errors as any)?.title}
          helperText={(errors as any)?.title?.message}
          margin="normal"
          fullWidth
          InputLabelProps={{ shrink: true }}
          type="text"
          label={translate("categories.fields.title")}
          name="title"
        />
      </Box>
    </Edit>
  );
};
