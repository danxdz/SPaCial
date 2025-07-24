import streamlit as st
from utils.mongo import get_db
from bson import ObjectId
import os
from PIL import Image
import io

# Pasta para guardar as imagens carregadas
# Mude para "uploads" se essa for a sua pasta raiz de uploads
IMG_UPLOAD_DIR = "uploads" 
os.makedirs(IMG_UPLOAD_DIR, exist_ok=True)

def app(t):
    st.title(t("manage_ateliers", "Gerir Ateliers"))
    st.markdown(t("manage_ateliers_desc", "Aqui pode adicionar, editar e remover ateliers, e gerir as suas imagens."))

    db = get_db()
    ateliers_collection = db.ateliers

    # --- Formulário para Adicionar/Editar Atelier ---
    st.subheader(t("add_edit_atelier", "Adicionar/Editar Atelier"))

    # Selecionar um atelier existente para edição
    existing_ateliers = list(ateliers_collection.find())
    
    # Criar uma lista de nomes para o selectbox, incluindo a opção "Novo Atelier"
    atelier_options = [{"_id": None, "name": "-- " + t("new_atelier", "Novo Atelier") + " --"}] + existing_ateliers
    
    # Usar um format_func para exibir o nome no selectbox
    selected_atelier_dict = st.selectbox(
        t("select_atelier_to_edit", "Selecionar Atelier para Editar:"),
        options=atelier_options,
        format_func=lambda x: x["name"],
        key="select_atelier_form"
    )

    current_atelier = selected_atelier_dict if selected_atelier_dict.get("_id") else None

    with st.form(key="atelier_form"):
        # Preencher campos com dados do atelier selecionado ou vazios para novo
        name = st.text_input(t("atelier_name", "Nome do Atelier"), value=current_atelier["name"] if current_atelier else "", key="atelier_name_input")
        description = st.text_area(t("description", "Descrição"), value=current_atelier.get("description", "") if current_atelier else "", key="atelier_desc_input")
        zone = st.text_input(t("zone", "Zona"), value=current_atelier.get("zone", "") if current_atelier else "", key="atelier_zone_input")
        capacity = st.number_input(t("capacity", "Capacidade Máxima"), min_value=0, value=current_atelier.get("capacity", 0) if current_atelier else 0, key="atelier_capacity_input")
        
        # Upload de Imagem/Ícone
        uploaded_file = st.file_uploader(t("upload_image", "Carregar Imagem/Ícone (PNG, JPG, GIF)"), type=["png", "jpg", "jpeg", "gif"], key="atelier_image_uploader")

        # Exibir imagem existente, se houver
        if current_atelier and current_atelier.get("image_path"):
            image_full_path = os.path.join(IMG_UPLOAD_DIR, os.path.basename(current_atelier["image_path"]))
            if os.path.exists(image_full_path):
                st.image(image_full_path, caption=t("current_image", "Imagem Atual"), width=150)
            else:
                st.warning(t("image_not_found_on_disk", "Imagem referenciada não encontrada no disco."))
        elif current_atelier and current_atelier.get("image_base64"): # Se estiver a guardar base64
             st.image(f"data:image/png;base64,{current_atelier['image_base64']}", caption=t("current_image", "Imagem Atual"), width=150)


        col1, col2 = st.columns(2)

        submitted = col1.form_submit_button(t("save_atelier", "Guardar Atelier"))
        delete_button = col2.form_submit_button(t("delete_atelier", "Apagar Atelier"))


        if submitted:
            if not name:
                st.error(t("name_required", "O nome do Atelier é obrigatório."))
                st.stop()

            atelier_data = {
                "name": name,
                "description": description,
                "zone": zone,
                "capacity": capacity
            }

            # Lidar com o upload da imagem
            if uploaded_file is not None:
                # Gerar um nome de ficheiro único para evitar colisões
                file_extension = uploaded_file.name.split(".")[-1]
                # Usar o nome do atelier para o nome do ficheiro para facilitar a associação
                image_filename = f"{name.replace(' ', '_').lower()}.{file_extension}"
                image_path_on_disk = os.path.join(IMG_UPLOAD_DIR, image_filename)
                
                with open(image_path_on_disk, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                atelier_data["image_path"] = image_path_on_disk # Guardar o caminho no DB
                st.success(t("image_uploaded", f"Imagem '{uploaded_file.name}' carregada com sucesso!"))
            
            # Lógica para salvar/atualizar
            if current_atelier:
                # Atualizar atelier existente
                ateliers_collection.update_one({"_id": current_atelier["_id"]}, {"$set": atelier_data})
                st.success(t("atelier_updated", f"Atelier '{name}' atualizado com sucesso!"))
            else:
                # Adicionar novo atelier
                if ateliers_collection.find_one({"name": name}):
                    st.error(t("atelier_exists", "Um atelier com este nome já existe. Por favor, escolha outro nome."))
                    st.stop()
                else:
                    ateliers_collection.insert_one(atelier_data)
                    st.success(t("atelier_added", f"Atelier '{name}' adicionado com sucesso!"))
            
            st.rerun() # Recarregar a página para atualizar a lista e o formulário

        if delete_button and current_atelier:
            if st.checkbox(t("confirm_delete", f"Tem certeza que quer apagar o atelier '{current_atelier['name']}'? Todos os postos de trabalho associados a este atelier precisarão de ser reatribuídos ou apagados."), key="confirm_delete_atelier_checkbox"):
                
                # Opcional: Remover a imagem do disco
                if current_atelier.get("image_path") and os.path.exists(current_atelier["image_path"]):
                    os.remove(current_atelier["image_path"])
                    st.info(t("image_removed", "Imagem do atelier removida do disco."))
                
                # NOTA: CONSIDERE O QUE FAZER COM OS POSTOS DE TRABALHO CUJO atelier_id SE REFERE A ESTE ATELIER
                # Opções: 
                # 1. Apagar os postos de trabalho associados (cascata)
                # 2. Definir o atelier_id dos postos de trabalho como None
                # Por agora, vou apenas avisar e deixar que o admin_workstations.py lide com isso.
                
                ateliers_collection.delete_one({"_id": current_atelier["_id"]})
                st.success(t("atelier_deleted", f"Atelier '{current_atelier['name']}' apagado com sucesso!"))
                st.rerun()

    st.markdown("---")

    # --- Listagem de Ateliers ---
    st.subheader(t("current_ateliers", "Ateliers Atuais"))
    ateliers_list = list(ateliers_collection.find())

    if ateliers_list:
        for i, atelier in enumerate(ateliers_list):
            st.markdown(f"**{t('name', 'Nome')}:** {atelier.get('name', 'N/A')}")
            st.markdown(f"**{t('zone', 'Zona')}:** {atelier.get('zone', 'N/A')}")
            st.markdown(f"**{t('capacity', 'Capacidade')}:** {atelier.get('capacity', 'N/A')}")
            st.markdown(f"**{t('description', 'Descrição')}:** {atelier.get('description', 'N/A')}")
            
            # Exibir imagem na lista
            if atelier.get("image_path"):
                image_full_path_list = os.path.join(IMG_UPLOAD_DIR, os.path.basename(atelier["image_path"]))
                if os.path.exists(image_full_path_list):
                    st.image(image_full_path_list, caption=atelier.get("name", ""), width=100)
                else:
                    st.warning(t("image_not_found_list", "Imagem não encontrada."))
            elif atelier.get("image_base64"):
                st.image(f"data:image/png;base64,{atelier['image_base64']}", caption=atelier.get("name", ""), width=100)
            else:
                st.info(t("no_image_available", "Nenhuma imagem disponível."))
            
            st.markdown("---")
    else:
        st.info(t("no_ateliers_found", "Nenhum atelier encontrado. Adicione um acima."))