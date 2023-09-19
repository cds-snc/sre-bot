import { IResourceComponentsProps, useTranslate } from "@refinedev/core";
import { Edit, useForm, useSelect } from "@refinedev/mantine";
import { NumberInput, TextInput, Textarea, Select } from "@mantine/core";

export const BlogPostEdit: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const {
    getInputProps,
    saveButtonProps,
    setFieldValue,
    refineCore: { queryResult },
  } = useForm({
    initialValues: {
      id: "",
      title: "",
      content: "",
      category: { id: "" },
      status: "",
      createdAt: "",
    },
  });

  const blogPostsData = queryResult?.data?.data;

  const { selectProps: categorySelectProps } = useSelect({
    resource: "categories",
    defaultValue: blogPostsData?.category?.id,
  });

  return (
    <Edit saveButtonProps={saveButtonProps}>
      <NumberInput
        mt="sm"
        disabled
        label={translate("blog_posts.fields.id")}
        {...getInputProps("id")}
      />
      <TextInput
        mt="sm"
        label={translate("blog_posts.fields.title")}
        {...getInputProps("title")}
      />
      <Textarea
        mt="sm"
        label={translate("blog_posts.fields.content")}
        autosize
        {...getInputProps("content")}
      />
      <Select
        mt="sm"
        label={translate("blog_posts.fields.category")}
        {...getInputProps("category.id")}
        {...categorySelectProps}
      />
      <TextInput
        mt="sm"
        label={translate("blog_posts.fields.status")}
        {...getInputProps("status")}
      />
      {/* 
                    DatePicker component is not included in "@refinedev/mantine" package.
                    To use a <DatePicker> component, you can follow the official documentation for Mantine.
                    
                    Docs: https://mantine.dev/dates/date-picker/
                */}
      <TextInput
        mt="sm"
        label={translate("blog_posts.fields.createdAt")}
        {...getInputProps("createdAt")}
      />
    </Edit>
  );
};
