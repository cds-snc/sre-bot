import React from "react";
import {
  useDataGrid,
  EditButton,
  ShowButton,
  DeleteButton,
  List,
} from "@refinedev/mui";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import { IResourceComponentsProps, useTranslate } from "@refinedev/core";

export const CategoryList: React.FC<IResourceComponentsProps> = () => {
  const translate = useTranslate();
  const { dataGridProps } = useDataGrid();

  const columns = React.useMemo<GridColDef[]>(
    () => [
      {
        field: "id",
        headerName: translate("categories.fields.id"),
        type: "number",
        minWidth: 50,
      },
      {
        field: "title",
        flex: 1,
        headerName: translate("categories.fields.title"),
        minWidth: 200,
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
    [translate]
  );

  return (
    <List>
      <DataGrid {...dataGridProps} columns={columns} autoHeight />
    </List>
  );
};
