import React from "react";
import {
  useDataGrid,
  EditButton,
  ShowButton,
  DeleteButton,
  List,
  MarkdownField,
  DateField,
} from "@refinedev/mui";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import {
  IResourceComponentsProps,
  useTranslate,
  useMany,
} from "@refinedev/core";

export const BlogPostList: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const { dataGridProps } = useDataGrid();

  const { data: categoryData, isLoading: categoryIsLoading } = useMany({
    resource: "categories",
    ids: dataGridProps?.rows?.map((item: any) => item?.category?.id) ?? [],
    queryOptions: {
      enabled: !!dataGridProps?.rows,
    },
  });

  const columns = React.useMemo<GridColDef[]>(
    () => [
      {
        field: "id",
        headerName: translate("blog_posts.fields.id"),
        type: "number",
        minWidth: 50,
      },
      {
        field: "title",
        flex: 1,
        headerName: translate("blog_posts.fields.title"),
        minWidth: 200,
      },
      {
        field: "content",
        flex: 1,
        headerName: translate("blog_posts.fields.content"),
        minWidth: 250,
        renderCell: function render({ value }) {
          return <MarkdownField value={(value ?? "").slice(0, 80) + "..."} />;
        },
      },
      {
        field: "category",
        flex: 1,
        headerName: translate("blog_posts.fields.category"),
        valueGetter: ({ row }) => {
          const value = row?.category?.id;

          return value;
        },
        minWidth: 300,
        renderCell: function render({ value }) {
          return categoryIsLoading ? (
            <>Loading...</>
          ) : (
            categoryData?.data?.find((item) => item.id === value)?.title
          );
        },
      },
      {
        field: "status",
        flex: 1,
        headerName: translate("blog_posts.fields.status"),
        minWidth: 200,
      },
      {
        field: "createdAt",
        flex: 1,
        headerName: translate("blog_posts.fields.createdAt"),
        minWidth: 250,
        renderCell: function render({ value }) {
          return <DateField value={value} />;
        },
      },
      {
        field: "actions",
        headerName: translate("table.actions"),
        sortable: false,
        renderCell: function render({ row }) {
          return (
            <>
              <EditButton hideText recordItemId={row.id} />
              <ShowButton hideText recordItemId={row.id} />
              <DeleteButton hideText recordItemId={row.id} />
            </>
          );
        },
        align: "center",
        headerAlign: "center",
        minWidth: 80,
      },
    ],
    [translate, categoryData?.data]
  );

  return (
    <List>
      <DataGrid {...dataGridProps} columns={columns} autoHeight />
    </List>
  );
};
