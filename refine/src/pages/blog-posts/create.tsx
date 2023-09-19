import { IResourceComponentsProps, useTranslate } from "@refinedev/core";
import { Create, useForm, useSelect } from "@refinedev/mantine";
import { TextInput, Textarea, Select } from "@mantine/core";

export const BlogPostCreate: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const {
    getInputProps,
    saveButtonProps,
    setFieldValue,
    refineCore: { formLoading },
  } = useForm({
    initialValues: {
      title: "",
      content: "",
      category: { id: "" },
      status: "",
      createdAt: "",
    },
  });

  const { selectProps: categorySelectProps } = useSelect({
    resource: "categories",
  });

  return (
    <Create isLoading={formLoading} saveButtonProps={saveButtonProps}>
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
    </Create>
  );
};
