import streamlit as st
from utils.mongo import get_db
from bson import ObjectId
import os
from PIL import Image
import io

# Pasta para guardar as imagens carregadas
IMG_UPLOAD_DIR = "uploads" 
os.makedirs(IMG_UPLOAD_DIR, exist_ok=True)

def app(t):
    st.title(t("manage_workstations", "Gerir Postos de Trabalho"))
    st.markdown(t("manage_workstations_desc", "Aqui pode adicionar, editar e remover postos de trabalho e associá-los a ateliers."))

    db = get_db()
    workstations_collection = db.workstations
    ateliers_collection = db.ateliers

    # --- Carregar Ateliers para o seletor ---
    all_ateliers = list(ateliers_collection.find())
    atelier_options_map = {a["name"]: str(a["_id"]) for a in all_ateliers}
    atelier_names_list = list(atelier_options_map.keys())
    
    # Adicionar opção "Nenhum Atelier" para casos onde um posto de trabalho não está associado
    atelier_names_list.insert(0, "-- " + t("select_atelier_dropdown", "Selecionar Atelier") + " --")


    # --- Formulário para Adicionar/Editar Posto de Trabalho ---
    st.subheader(t("add_edit_workstation", "Adicionar/Editar Posto de Trabalho"))

    # Selecionar um posto de trabalho existente para edição
    existing_workstations = list(workstations_collection.find())
    
    workstation_options = [{"_id": None, "name": "-- " + t("new_workstation", "Novo Posto de Trabalho") + " --"}] + existing_workstations
    
    selected_workstation_dict = st.selectbox(
        t("select_workstation_to_edit", "Selecionar Posto de Trabalho para Editar:"),
        options=workstation_options,
        format_func=lambda x: x["name"],
        key="select_workstation_form"
    )

    current_workstation = selected_workstation_dict if selected_workstation_dict.get("_id") else None

    with st.form(key="workstation_form"):
        # Preencher campos com dados do posto de trabalho selecionado ou vazios para novo
        name = st.text_input(t("workstation_name", "Nome do Posto de Trabalho"), value=current_workstation["name"] if current_workstation else "", key="workstation_name_input")
        description = st.text_area(t("description", "Descrição"), value=current_workstation.get("description", "") if current_workstation else "", key="workstation_desc_input")
        machine_type = st.text_input(t("machine_type", "Tipo de Máquina"), value=current_workstation.get("machine_type", "") if current_workstation else "", key="workstation_machine_input")
        status_options = [t("active", "Ativo"), t("inactive", "Inativo"), t("maintenance", "Manutenção")]
        status = st.selectbox(t("status", "Estado"), options=status_options, index=status_options.index(current_workstation.get("status", status_options[0])) if current_workstation else 0, key="workstation_status_input")
        
        # Seleção de Atelier para associação
        # Se estiver a editar, pré-selecionar o atelier atual
        default_atelier_index = 0
        if current_workstation and current_workstation.get("atelier_id"):
            for idx, atelier_name in enumerate(atelier_names_list):
                if atelier_name != "-- " + t("select_atelier_dropdown", "Selecionar Atelier") + " --" and atelier_options_map.get(atelier_name) == str(current_workstation["atelier_id"]):
                    default_atelier_index = idx
                    break

        selected_atelier_name_for_ws = st.selectbox(
            t("associate_with_atelier", "Associar com Atelier:"),
            options=atelier_names_list,
            index=default_atelier_index,
            key="workstation_atelier_select"
        )
        
        # Upload de Imagem/Ícone
        uploaded_file = st.file_uploader(t("upload_image", "Carregar Imagem/Ícone (PNG, JPG, GIF)"), type=["png", "jpg", "jpeg", "gif"], key="workstation_image_uploader")

        # Exibir imagem existente, se houver
        if current_workstation and current_workstation.get("image_path"):
            image_full_path = os.path.join(IMG_UPLOAD_DIR, os.path.basename(current_workstation["image_path"]))
            if os.path.exists(image_full_path):
                st.image(image_full_path, caption=t("current_image", "Imagem Atual"), width=150)
            else:
                st.warning(t("image_not_found_on_disk", "Imagem referenciada não encontrada no disco."))
        elif current_workstation and current_workstation.get("image_base64"):
             st.image(f"data:image/png;base64,{current_workstation['image_base64']}", caption=t("current_image", "Imagem Atual"), width=150)

        col1, col2 = st.columns(2)

        submitted = col1.form_submit_button(t("save_workstation", "Guardar Posto de Trabalho"))
        delete_button = col2.form_submit_button(t("delete_workstation", "Apagar Posto de Trabalho"))


        if submitted:
            if not name:
                st.error(t("name_required", "O nome do Posto de Trabalho é obrigatório."))
                st.stop()

            # Obter o ID do atelier selecionado
            atelier_id_to_save = None
            if selected_atelier_name_for_ws != "-- " + t("select_atelier_dropdown", "Selecionar Atelier") + " --":
                atelier_id_to_save = atelier_options_map[selected_atelier_name_for_ws]

            workstation_data = {
                "name": name,
                "description": description,
                "machine_type": machine_type,
                "status": status,
                "atelier_id": atelier_id_to_save # Guarda o ID do atelier
            }

            # Lidar com o upload da imagem
            if uploaded_file is not None:
                file_extension = uploaded_file.name.split(".")[-1]
                image_filename = f"{name.replace(' ', '_').lower()}_ws.{file_extension}" # Adicionado _ws para evitar colisões
                image_path_on_disk = os.path.join(IMG_UPLOAD_DIR, image_filename)
                
                with open(image_path_on_disk, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                workstation_data["image_path"] = image_path_on_disk
                st.success(t("image_uploaded", f"Imagem '{uploaded_file.name}' carregada com sucesso!"))
            
            # Lógica para salvar/atualizar
            if current_workstation:
                workstations_collection.update_one({"_id": current_workstation["_id"]}, {"$set": workstation_data})
                st.success(t("workstation_updated", f"Posto de Trabalho '{name}' atualizado com sucesso!"))
            else:
                if workstations_collection.find_one({"name": name}):
                    st.error(t("workstation_exists", "Um posto de trabalho com este nome já existe. Por favor, escolha outro nome."))
                    st.stop()
                else:
                    workstations_collection.insert_one(workstation_data)
                    st.success(t("workstation_added", f"Posto de Trabalho '{name}' adicionado com sucesso!"))
            
            st.rerun()

        if delete_button and current_workstation:
            if st.checkbox(t("confirm_delete", f"Tem certeza que quer apagar o posto de trabalho '{current_workstation['name']}'?"), key="confirm_delete_workstation_checkbox"):
                
                # Opcional: Remover a imagem do disco
                if current_workstation.get("image_path") and os.path.exists(current_workstation["image_path"]):
                    os.remove(current_workstation["image_path"])
                    st.info(t("image_removed", "Imagem do posto de trabalho removida do disco."))
                
                workstations_collection.delete_one({"_id": current_workstation["_id"]})
                st.success(t("workstation_deleted", f"Posto de Trabalho '{current_workstation['name']}' apagado com sucesso!"))
                st.rerun()

    st.markdown("---")

    # --- Listagem de Postos de Trabalho ---
    st.subheader(t("current_workstations", "Postos de Trabalho Atuais"))
    workstations_list = list(workstations_collection.find())

    if workstations_list:
        for i, ws in enumerate(workstations_list):
            st.markdown(f"**{t('name', 'Nome')}:** {ws.get('name', 'N/A')}")
            st.markdown(f"**{t('description', 'Descrição')}:** {ws.get('description', 'N/A')}")
            st.markdown(f"**{t('machine_type', 'Tipo de Máquina')}:** {ws.get('machine_type', 'N/A')}")
            st.markdown(f"**{t('status', 'Estado')}:** {ws.get('status', 'N/A')}")
            
            # Exibir o atelier associado (se houver)
            if ws.get("atelier_id"):
                linked_atelier = ateliers_collection.find_one({"_id": ObjectId(ws["atelier_id"])})
                if linked_atelier:
                    st.markdown(f"**{t('associated_atelier', 'Atelier Associado')}:** {linked_atelier.get('name', 'N/A')}")
                else:
                    st.warning(t("atelier_not_found", f"Atelier associado com ID {ws['atelier_id']} não encontrado!"))
            else:
                st.info(t("no_atelier_associated", "Nenhum atelier associado."))

            # Exibir imagem na lista
            if ws.get("image_path"):
                image_full_path_list = os.path.join(IMG_UPLOAD_DIR, os.path.basename(ws["image_path"]))
                if os.path.exists(image_full_path_list):
                    st.image(image_full_path_list, caption=ws.get("name", ""), width=100)
                else:
                    st.warning(t("image_not_found_list", "Imagem não encontrada."))
            elif ws.get("image_base64"):
                st.image(f"data:image/png;base64,{ws['image_base64']}", caption=ws.get("name", ""), width=100)
            else:
                st.info(t("no_image_available", "Nenhuma imagem disponível."))
            
            st.markdown("---")
    else:
        st.info(t("no_workstations_found", "Nenhum posto de trabalho encontrado. Adicione um acima."))