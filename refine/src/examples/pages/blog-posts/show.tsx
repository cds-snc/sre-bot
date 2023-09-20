import {
  useShow,
  IResourceComponentsProps,
  useTranslate,
  useOne,
} from "@refinedev/core";
import {
  Show,
  NumberField,
  TextFieldComponent as TextField,
  MarkdownField,
  DateField,
} from "@refinedev/mui";
import { Typography, Stack } from "@mui/material";

export const BlogPostShow: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const { queryResult } = useShow();
  const { data, isLoading } = queryResult;

  const record = data?.data;

  const { data: categoryData, isLoading: categoryIsLoading } = useOne({
    resource: "categories",
    id: record?.category?.id || "",
    queryOptions: {
      enabled: !!record,
    },
  });

  return (
    <Show isLoading={isLoading}>
      <Stack gap={1}>
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.id")}
        </Typography>
        <NumberField value={record?.id ?? ""} />
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.title")}
        </Typography>
        <TextField value={record?.title} />
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.content")}
        </Typography>
        <MarkdownField value={record?.content} />
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.category")}
        </Typography>

        {categoryIsLoading ? <>Loading...</> : <>{categoryData?.data?.title}</>}
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.status")}
        </Typography>
        <TextField value={record?.status} />
        <Typography variant="body1" fontWeight="bold">
          {translate("blog_posts.fields.createdAt")}
        </Typography>
        <DateField value={record?.createdAt} />
      </Stack>
    </Show>
  );
};
