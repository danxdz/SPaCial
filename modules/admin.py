import streamlit as st
from utils.mongo import get_db
import bson
import pandas as pd
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

db = get_db()

def convert_objectid_to_str(docs):
    """Convert ObjectId to string for display and Arrow compatibility"""
    if isinstance(docs, list):
        for doc in docs:
            for key, value in doc.items():
                if isinstance(value, bson.ObjectId):
                    doc[key] = str(value)
                elif key == "_id" and isinstance(value, str):
                    # Keep _id as string
                    continue
                elif isinstance(value, dict):
                    # Recursively handle nested ObjectIds
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, bson.ObjectId):
                            value[nested_key] = str(nested_value)
        return docs
    elif isinstance(docs, dict):
        for key, value in docs.items():
            if isinstance(value, bson.ObjectId):
                docs[key] = str(value)
            elif isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, bson.ObjectId):
                        value[nested_key] = str(nested_value)
        return docs
    return docs

def safe_dataframe_conversion(docs):
    """Safely convert documents to DataFrame with proper type handling"""
    if not docs:
        return pd.DataFrame()
    
    # Convert ObjectIds first
    clean_docs = convert_objectid_to_str(docs.copy() if isinstance(docs, list) else [docs])
    
    # Create DataFrame with explicit type conversion
    df = pd.DataFrame(clean_docs)
    
    # Handle problematic columns
    for col in df.columns:
        # Convert any remaining ObjectId-like strings or objects
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
    
    return df.fillna("")

def get_collections_with_relations():
    """Get all collections and detect potential parent-child relationships"""
    collections = [c for c in db.list_collection_names() if c != "schemas"]
    relations = {}
    
    for collection in collections:
        sample_docs = list(db[collection].find({}).limit(10))
        sample_docs = convert_objectid_to_str(sample_docs)
        
        # Look for fields that end with _id and might reference other collections
        reference_fields = {}
        for doc in sample_docs:
            for field, value in doc.items():
                if field.endswith('_id') and field != '_id':
                    # Extract potential collection name
                    potential_collection = field[:-3]  # Remove _id suffix
                    if potential_collection in collections:
                        reference_fields[field] = potential_collection
                # Check for any hierarchy field (not just parent_id)
                elif any(hierarchy_word in field.lower() for hierarchy_word in ['parent', 'pai', 'superior']) and field.endswith('_id'):
                    # Self-referencing hierarchy
                    reference_fields[field] = collection
        
        relations[collection] = reference_fields
    
    return collections, relations

def get_hierarchy_fields(docs):
    """Get all fields that could potentially be hierarchy fields"""
    potential_fields = set()
    
    for doc in docs:
        for field in doc.keys():
            if field.endswith('_id') and field != '_id':
                potential_fields.add(field)
            elif 'parent' in field.lower():
                potential_fields.add(field)
    
    return list(potential_fields)

def create_hierarchy_view(collection_name, parent_field="parent_id"):
    """Create a hierarchical view with drag-and-drop functionality"""
    docs = list(db[collection_name].find({}))
    docs = convert_objectid_to_str(docs)
    
    # Find root nodes (no parent field or parent field is null)
    roots = [doc for doc in docs if not doc.get(parent_field) or doc.get(parent_field) in [None, "", "None"]]
    
    def build_tree_display(doc, level=0):
        indent = "  " * level
        name = doc.get("name", doc.get("title", doc["_id"]))
        
        # Create columns for drag-and-drop controls
        col1, col2, col3, col4 = st.columns([0.7, 0.1, 0.1, 0.1])
        
        with col1:
            st.write(f"{indent}📁 **{name}** (`ID: {doc['_id']}`)")
        
        with col2:
            if st.button("⬆️", key=f"up_{doc['_id']}", help="Mover para cima"):
                move_item_up(collection_name, doc['_id'], parent_field, docs)
        
        with col3:
            if st.button("⬇️", key=f"down_{doc['_id']}", help="Mover para baixo"):
                move_item_down(collection_name, doc['_id'], parent_field, docs)
        
        with col4:
            if st.button("📝", key=f"edit_{doc['_id']}", help="Editar rápido"):
                edit_item_inline(collection_name, doc)
        
        # Find children
        children = [d for d in docs if d.get(parent_field) == doc["_id"]]
        for child in children:
            build_tree_display(child, level + 1)
    
    if roots:
        st.markdown(f"### 🌳 Estrutura Hierárquica (Campo: {parent_field})")
        
        # Add drag-and-drop interface
        with st.expander("🎛️ Controles de Hierarquia", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Mover Item:**")
                if docs:
                    item_to_move = st.selectbox(
                        "Selecionar item:",
                        [doc["_id"] for doc in docs],
                        format_func=lambda x: next(
                            (doc.get("name", doc.get("title", f"ID: {x}")) 
                             for doc in docs if doc["_id"] == x), x
                        ),
                        key="move_item_select"
                    )
                    
                    new_parent = st.selectbox(
                        "Novo pai:",
                        [None] + [doc["_id"] for doc in docs if doc["_id"] != item_to_move],
                        format_func=lambda x: "(Raiz)" if x is None else next(
                            (doc.get("name", doc.get("title", f"ID: {x}")) 
                             for doc in docs if doc["_id"] == x), str(x)
                        ),
                        key="new_parent_select"
                    )
                    
                    if st.button("🔄 Executar Movimento", type="primary"):
                        move_item_to_parent(collection_name, item_to_move, new_parent, parent_field)
            
            with col2:
                st.markdown("**Operações em Lote:**")
                if st.button("🔄 Reorganizar Automaticamente"):
                    reorganize_hierarchy(collection_name, parent_field)
                
                if st.button("📊 Gerar Relatório de Hierarquia"):
                    generate_hierarchy_report(collection_name, parent_field, docs)
        
        st.markdown("---")
        
        for root in roots:
            build_tree_display(root)
    else:
        st.info(f"Não há elementos raiz (todos têm {parent_field} definido)")

def move_item_to_parent(collection_name, item_id, new_parent_id, parent_field):
    """Move an item to a new parent"""
    try:
        update_data = {parent_field: new_parent_id}
        if new_parent_id is None:
            update_data = {parent_field: None}
        
        result = db[collection_name].update_one(
            {"_id": bson.ObjectId(item_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            st.success("✅ Item movido com sucesso!")
            st.rerun()
        else:
            st.warning("Nenhuma alteração foi feita.")
    except Exception as e:
        st.error(f"Erro ao mover item: {e}")

def move_item_up(collection_name, item_id, parent_field, docs):
    """Move item up in the hierarchy"""
    # Implementation for moving items up - simplified for this example
    st.info("Funcionalidade de mover para cima será implementada")

def move_item_down(collection_name, item_id, parent_field, docs):
    """Move item down in the hierarchy"""
    # Implementation for moving items down - simplified for this example
    st.info("Funcionalidade de mover para baixo será implementada")

def edit_item_inline(collection_name, doc):
    """Quick inline editing"""
    with st.popover(f"Editar {doc.get('name', doc['_id'])}", use_container_width=True):
        with st.form(f"edit_form_{doc['_id']}"):
            edited_data = {}
            
            for key, value in doc.items():
                if key == '_id':
                    st.text_input("ID (somente leitura)", value=value, disabled=True)
                    continue
                
                if isinstance(value, bool):
                    edited_data[key] = st.checkbox(key, value=value)
                elif isinstance(value, (int, float)):
                    edited_data[key] = st.number_input(key, value=value)
                else:
                    edited_data[key] = st.text_input(key, value=str(value) if value else "")
            
            if st.form_submit_button("💾 Salvar", type="primary"):
                save_inline_edit(collection_name, doc['_id'], edited_data)

def save_inline_edit(collection_name, doc_id, edited_data):
    """Save inline edits"""
    try:
        # Clean empty values
        clean_data = {k: v for k, v in edited_data.items() 
                     if v not in [None, "", "None"]}
        
        result = db[collection_name].update_one(
            {"_id": bson.ObjectId(doc_id)},
            {"$set": clean_data}
        )
        
        if result.modified_count > 0:
            st.success("✅ Dados atualizados!")
            st.rerun()
        else:
            st.info("Nenhuma alteração detectada.")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def reorganize_hierarchy(collection_name, parent_field):
    """Automatically reorganize hierarchy"""
    st.info("Reorganização automática da hierarquia será implementada")

def generate_hierarchy_report(collection_name, parent_field, docs):
    """Generate hierarchy analysis report"""
    with st.expander("📊 Relatório de Hierarquia", expanded=True):
        # Calculate statistics
        roots = [doc for doc in docs if not doc.get(parent_field)]
        orphans = [doc for doc in docs if doc.get(parent_field) and 
                  not any(d["_id"] == doc.get(parent_field) for d in docs)]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Nós", len(docs))
        with col2:
            st.metric("Nós Raiz", len(roots))
        with col3:
            st.metric("Nós Órfãos", len(orphans))
        with col4:
            # Calculate max depth
            max_depth = calculate_max_depth(docs, parent_field)
            st.metric("Profundidade Máxima", max_depth)
        
        if orphans:
            st.warning(f"⚠️ {len(orphans)} nós órfãos encontrados!")
            with st.expander("Ver Nós Órfãos"):
                for orphan in orphans:
                    st.write(f"- {orphan.get('name', orphan['_id'])} (referencia: {orphan.get(parent_field)})")

def calculate_max_depth(docs, parent_field):
    """Calculate maximum depth of hierarchy"""
    def get_depth(doc_id, current_depth=0):
        children = [d for d in docs if d.get(parent_field) == doc_id]
        if not children:
            return current_depth
        return max(get_depth(child["_id"], current_depth + 1) for child in children)
    
    roots = [doc for doc in docs if not doc.get(parent_field)]
    if not roots:
        return 0
    
    return max(get_depth(root["_id"]) for root in roots)

def get_reference_options(collection_name, field_name, relations):
    """Get options for reference fields"""
    if field_name in relations.get(collection_name, {}):
        ref_collection = relations[collection_name][field_name]
        docs = list(db[ref_collection].find({}))
        docs = convert_objectid_to_str(docs)
        
        options = [None] + [doc["_id"] for doc in docs]
        labels = ["(Selecionar)"] + [
            doc.get("name", doc.get("title", f"ID: {doc['_id']}")) 
            for doc in docs
        ]
        return options, labels, docs
    return [], [], []

def advanced_crud_interface(collection_name, docs, relations):
    """Advanced CRUD interface with better table management"""
    st.markdown("### 📝 Interface CRUD")
    
    # Search and filter
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 Buscar documentos:", placeholder="Busque por qualquer campo...")
    
    with col2:
        show_enriched = st.checkbox("Mostrar dados relacionados", value=True)
    
    with col3:
        items_per_page = st.selectbox("Itens por página:", [10, 25, 50, 100], index=1)
    
    # Filter documents
    filtered_docs = docs
    if search_term:
        filtered_docs = []
        for doc in docs:
            if any(search_term.lower() in str(v).lower() for v in doc.values()):
                filtered_docs.append(doc)
    
    # Pagination
    total_items = len(filtered_docs)
    total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        current_page = st.selectbox(
            f"Página (Total: {total_pages})",
            range(1, total_pages + 1),
            key="page_selector"
        ) - 1
    
    # Get current page items
    start_idx = current_page * items_per_page
    end_idx = start_idx + items_per_page
    current_docs = filtered_docs[start_idx:end_idx]
    
    
    # Original editable table
    st.markdown(f"#### ✏️ Tabela Editável ({len(current_docs)} de {total_items} documentos)")
    
    if current_docs:
        # Convert to safe DataFrame
        df = safe_dataframe_conversion(current_docs)
        
        # Configure column types
        column_config = {}
        for col in df.columns:
            if col.endswith('_id') and col != '_id':
                column_config[col] = st.column_config.TextColumn(
                    col,
                    help=f"Campo de referência: {col}",
                    width="medium"
                )
            elif col == '_id':
                column_config[col] = st.column_config.TextColumn(
                    col,
                    help="ID do documento (somente leitura)",
                    disabled=True,
                    width="small"
                )
        
        # Show editable data_editor
        edited_df = st.data_editor(
            df, 
            use_container_width=True,
            num_rows="dynamic",
            key=f"crud_editor_{current_page}",
            column_config=column_config,
            hide_index=True
        )
        
        # Advanced action buttons
        st.markdown("#### 🛠️ Ações Avançadas")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("💾 Salvar Todas as Alterações", type="primary"):
                save_all_changes(collection_name, edited_df, current_docs, start_idx)
        
        with col2:
            if st.button("🔄 Reverter Alterações"):
                st.rerun()
        
        with col3:
            # Bulk operations
            with st.popover("📦 Operações em Lote"):
                bulk_field = st.selectbox("Campo para operação:", df.columns.tolist())
                bulk_value = st.text_input("Novo valor:")
                
                if st.button("Aplicar a Todas as Linhas"):
                    if bulk_field and bulk_value:
                        apply_bulk_operation(collection_name, bulk_field, bulk_value, current_docs)
        
        with col4:
            # Export options
            with st.popover("📤 Exportar Dados"):
                export_format = st.selectbox("Formato:", ["JSON", "CSV", "Excel"])
                
                if st.button("Baixar"):
                    export_data(df, export_format, collection_name)
        
        # Row selection for deletion
        if len(edited_df) > 0:
            st.markdown("#### 🗑️ Gerenciar Exclusões")
            
            # Multi-select for deletion
            rows_to_delete = st.multiselect(
                "Selecionar linhas para deletar:",
                options=range(len(edited_df)),
                format_func=lambda x: f"Linha {x+1}: {edited_df.iloc[x].get('name', edited_df.iloc[x].get('_id', 'N/A'))}"
            )
            
            if rows_to_delete:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.warning(f"⚠️ {len(rows_to_delete)} linha(s) selecionada(s) para exclusão")
                
                with col2:
                    if st.button("🗑️ Confirmar Exclusão", type="secondary"):
                        delete_selected_rows(collection_name, edited_df, rows_to_delete)
    
    else:
        st.info("Nenhum documento encontrado com os critérios de busca.")


    
   

def save_all_changes(collection_name, edited_df, original_docs, start_idx):
    """Save all changes from the edited DataFrame"""
    update_count = 0
    insert_count = 0
    error_count = 0
    
    try:
        collection = db[collection_name]
        
        for idx, row in edited_df.iterrows():
            try:
                if idx >= len(original_docs):  # New row
                    new_doc = row.to_dict()
                    new_doc = {k: v for k, v in new_doc.items() 
                              if pd.notna(v) and v != "" and v != "nan"}
                    
                    if new_doc:
                        # Convert string IDs back to ObjectId where needed
                        new_doc = prepare_doc_for_save(new_doc)
                        collection.insert_one(new_doc)
                        insert_count += 1
                
                else:  # Existing row
                    doc_id = row["_id"]
                    if doc_id and doc_id != "":
                        new_doc = row.to_dict()
                        new_doc.pop("_id", None)
                        new_doc = {k: v for k, v in new_doc.items() if pd.notna(v)}
                        
                        # Convert string IDs back to ObjectId where needed
                        new_doc = prepare_doc_for_save(new_doc)
                        
                        result = collection.update_one(
                            {"_id": bson.ObjectId(doc_id)}, 
                            {"$set": new_doc}
                        )
                        
                        if result.modified_count > 0:
                            update_count += 1
            
            except Exception as e:
                error_count += 1
                st.error(f"Erro na linha {idx + 1}: {e}")
        
        # Show results
        if update_count > 0 or insert_count > 0:
            st.success(f"✅ Processamento concluído! Atualizados: {update_count}, Inseridos: {insert_count}")
            if error_count > 0:
                st.warning(f"⚠️ {error_count} erro(s) encontrado(s)")
            st.rerun()
        elif error_count > 0:
            st.error(f"❌ {error_count} erro(s) encontrado(s). Nenhuma alteração salva.")
        else:
            st.info("ℹ️ Nenhuma alteração detectada.")
    
    except Exception as e:
        st.error(f"Erro geral ao salvar: {e}")

def prepare_doc_for_save(doc):
    """Prepare document for saving, handling ObjectId conversion"""
    prepared_doc = {}
    
    for key, value in doc.items():
        if key.endswith('_id') and key != '_id' and value and value != "":
            try:
                # Try to convert to ObjectId if it's a valid ObjectId string
                if isinstance(value, str) and len(value) == 24:
                    prepared_doc[key] = bson.ObjectId(value)
                else:
                    prepared_doc[key] = value
            except:
                prepared_doc[key] = value
        else:
            prepared_doc[key] = value
    
    return prepared_doc

def apply_bulk_operation(collection_name, field, value, docs):
    """Apply bulk operation to multiple documents"""
    try:
        doc_ids = [bson.ObjectId(doc["_id"]) for doc in docs]
        
        # Prepare value for saving
        update_value = value
        if field.endswith('_id') and field != '_id' and value:
            try:
                if len(value) == 24:
                    update_value = bson.ObjectId(value)
            except:
                pass
        
        result = db[collection_name].update_many(
            {"_id": {"$in": doc_ids}},
            {"$set": {field: update_value}}
        )
        
        st.success(f"✅ {result.modified_count} documentos atualizados!")
        st.rerun()
    
    except Exception as e:
        st.error(f"Erro na operação em lote: {e}")

def delete_selected_rows(collection_name, df, rows_to_delete):
    """Delete selected rows"""
    delete_count = 0
    error_count = 0
    
    for idx in rows_to_delete:
        if idx < len(df):
            try:
                doc_id = df.iloc[idx]["_id"]
                if doc_id:
                    result = db[collection_name].delete_one({"_id": bson.ObjectId(doc_id)})
                    if result.deleted_count > 0:
                        delete_count += 1
                    else:
                        error_count += 1
            except Exception as e:
                error_count += 1
                st.error(f"Erro ao deletar linha {idx + 1}: {e}")
    
    if delete_count > 0:
        st.success(f"✅ {delete_count} documento(s) deletado(s)!")
        if error_count > 0:
            st.warning(f"⚠️ {error_count} erro(s) na exclusão")
        st.rerun()
    else:
        st.error("❌ Nenhum documento foi deletado")

def export_data(df, format_type, collection_name):
    """Export data in different formats"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{collection_name}_{timestamp}"
    
    if format_type == "JSON":
        json_data = df.to_json(orient='records', indent=2)
        st.download_button(
            label="📥 Baixar JSON",
            data=json_data,
            file_name=f"{filename}.json",
            mime="application/json"
        )
    
    elif format_type == "CSV":
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar CSV",
            data=csv_data,
            file_name=f"{filename}.csv",
            mime="text/csv"
        )
    
    elif format_type == "Excel":
        # Note: This would require openpyxl or xlsxwriter
        st.info("Funcionalidade Excel será implementada (requer biblioteca adicional)")

def get_related_documents(doc_id, collection_name, all_collections):
    """Find all documents that reference this document"""
    related = {}
    
    for coll_name in all_collections:
        if coll_name == collection_name:
            continue
            
        # Look for documents that reference this one
        refs = list(db[coll_name].find({f"{collection_name}_id": doc_id}))
        if refs:
            related[coll_name] = convert_objectid_to_str(refs)
        
        # Also check for parent_id references (if it's the same collection)
        if coll_name == collection_name:
            children = list(db[coll_name].find({"parent_id": doc_id}))
            if children:
                related["children"] = convert_objectid_to_str(children)
    
    return related

def app(lang, filters):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 15px; margin-bottom: 2rem;'>
            <h1 style='color: white; margin: 0; text-align: center;'>
                🗄️ MongoDB CRUD Manager Pro
            </h1>
            <p style='color: rgba(255,255,255,0.9); text-align: center; margin: 0.5rem 0 0 0;'>
                Gerenciamento CRUD Avançado com Drag-and-Drop
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Get collections and relations
    collections, relations = get_collections_with_relations()
    
    if not collections:
        st.error("Nenhuma coleção encontrada no banco de dados.")
        return

    # Collection selector with session state
    if "selected_collection" in st.session_state and st.session_state["selected_collection"] in collections:
        default_index = collections.index(st.session_state["selected_collection"])
    else:
        default_index = 0
    
    collection_name = st.selectbox(
        "📁 Selecionar Coleção", 
        collections,
        index=default_index,
        help="Escolha a coleção MongoDB para gerenciar"
    )

    if not collection_name:
        return

    collection = db[collection_name]
    docs = list(collection.find({}))
    docs = convert_objectid_to_str(docs)

    # Show collection info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Documentos", len(docs))
    with col2:
        if collection_name in relations and relations[collection_name]:
            st.metric("Relações", len(relations[collection_name]))
        else:
            st.metric("Relações", 0)
    with col3:
        hierarchy_fields = get_hierarchy_fields(docs)
        st.metric("Campos Hierárquicos", len(hierarchy_fields))

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 CRUD Pro", "🌳 Hierarquia", "🔗 Relações", "📊 Detalhes"])

    with tab1:
        advanced_crud_interface(collection_name, docs, relations)
        
        # Enhanced Add new document form
        st.markdown("---")
        st.markdown("### ➕ Formulário Inteligente de Inserção")
        
        with st.expander("Adicionar Novo Documento", expanded=not bool(docs)):
            # Get sample document structure if available
            sample_fields = {}
            if docs:
                for doc in docs[:5]:  # Use first 5 docs to determine structure
                    for field, value in doc.items():
                        if field not in sample_fields:
                            sample_fields[field] = type(value).__name__
            
            # Smart form generation
            create_smart_insertion_form(collection_name, sample_fields, relations)

    with tab2:
        st.markdown("### 🌳 Gestão Hierárquica Avançada")
        
        # Get potential hierarchy fields
        hierarchy_fields = get_hierarchy_fields(docs)
        
        if not hierarchy_fields:
            st.info("Nenhum campo hierárquico detectado.")
            create_hierarchy_field_manager(collection_name)
        else:
            # Select hierarchy field
            selected_hierarchy_field = st.selectbox(
                "🔧 Escolher campo hierárquico:",
                hierarchy_fields,
                help="Selecione qual campo usar para construir a hierarquia"
            )
            
            # Check if this field has hierarchical structure
            has_hierarchy = any(doc.get(selected_hierarchy_field) for doc in docs)
            
            if has_hierarchy:
                create_hierarchy_view(collection_name, selected_hierarchy_field)
            else:
                st.info(f"O campo '{selected_hierarchy_field}' existe mas não possui valores hierárquicos.")
                create_hierarchy_tools(collection_name, selected_hierarchy_field)

    with tab3:
        create_relations_manager(collection_name, relations, collections)

    with tab4:
        create_details_explorer(collection_name, docs, relations, collections)

def create_smart_insertion_form(collection_name, sample_fields, relations):
    """Create intelligent form for document insertion"""
    with st.form("smart_insert_form"):
        st.markdown("#### 📝 Formulário Inteligente")
        
        new_doc = {}
        
        # Organize fields into columns
        field_list = list(sample_fields.items())
        if field_list:
            mid_point = len(field_list) // 2
            col1, col2 = st.columns(2)
            
            # Left column
            with col1:
                st.markdown("**Campos Principais:**")
                for field, field_type in field_list[:mid_point]:
                    if field == '_id':
                        continue
                    new_doc[field] = create_smart_field_input(field, field_type, collection_name, relations)
            
            # Right column
            with col2:
                st.markdown("**Campos Adicionais:**")
                for field, field_type in field_list[mid_point:]:
                    if field == '_id':
                        continue
                    new_doc[field] = create_smart_field_input(field, field_type, collection_name, relations, key_suffix="_right")
        
        # Dynamic fields section
        st.markdown("---")
        st.markdown("**Campos Customizados:**")
        
        # Allow adding multiple custom fields
        num_custom_fields = st.number_input("Número de campos customizados:", min_value=0, max_value=10, value=0)
        
        for i in range(num_custom_fields):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                custom_field_name = st.text_input(f"Nome do campo {i+1}:", key=f"custom_name_{i}")
            with col2:
                custom_field_value = st.text_input(f"Valor {i+1}:", key=f"custom_value_{i}")
            with col3:
                field_type = st.selectbox(f"Tipo {i+1}", ["text", "number", "boolean"], key=f"custom_type_{i}")
            
            if custom_field_name and custom_field_value:
                if field_type == "number":
                    try:
                        new_doc[custom_field_name] = float(custom_field_value)
                    except:
                        new_doc[custom_field_name] = custom_field_value
                elif field_type == "boolean":
                    new_doc[custom_field_name] = custom_field_value.lower() in ['true', '1', 'yes', 'sim']
                else:
                    new_doc[custom_field_name] = custom_field_value
        
        # Form submission
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            validate_before_insert = st.checkbox("Validar antes de inserir", value=True)
        
        with col2:
            if st.form_submit_button("📤 Inserir Documento", type="primary", use_container_width=True):
                insert_smart_document(collection_name, new_doc, validate_before_insert)
        
        with col3:
            if st.form_submit_button("🔄 Limpar Formulário"):
                st.rerun()

def create_smart_field_input(field, field_type, collection_name, relations, key_suffix=""):
    """Create smart field input based on field type and relations"""
    key = f"{field}{key_suffix}"
    
    if field.endswith('_id') and field != '_id':
        # Reference field
        options, labels, ref_docs = get_reference_options(collection_name, field, relations)
        if options:
            selected = st.selectbox(
                f"{field} (Referência)",
                options,
                format_func=lambda x, labels=labels, options=options: 
                    labels[options.index(x)] if x in options else str(x),
                key=key
            )
            
            # Show preview of referenced data
            if selected and ref_docs:
                ref_doc = next((d for d in ref_docs if d["_id"] == selected), None)
                if ref_doc:
                    with st.expander(f"👁️ Preview de {field}", expanded=False):
                        preview_data = {k: v for k, v in ref_doc.items() if k not in ['_id']}
                        st.json(preview_data)
            
            return selected
        else:
            return st.text_input(f"{field}", key=key)
    
    elif field_type == 'bool':
        return st.checkbox(f"{field}", key=key)
    elif field_type in ['int', 'float']:
        return st.number_input(f"{field}", step=1 if field_type == 'int' else 0.01, key=key)
    elif field_type == 'datetime':
        return st.datetime_input(f"{field}", key=key)
    elif 'email' in field.lower():
        return st.text_input(f"{field}", placeholder="exemplo@email.com", key=key)
    elif 'url' in field.lower() or 'link' in field.lower():
        return st.text_input(f"{field}", placeholder="https://...", key=key)
    elif 'phone' in field.lower() or 'telefone' in field.lower():
        return st.text_input(f"{field}", placeholder="+55 11 99999-9999", key=key)
    else:
        return st.text_input(f"{field}", key=key)

def insert_smart_document(collection_name, new_doc, validate):
    """Insert document with smart validation"""
    try:
        # Clean empty fields
        clean_doc = {k: v for k, v in new_doc.items() 
                    if v not in [None, "", [], "None"] and pd.notna(v)}
        
        if not clean_doc:
            st.warning("⚠️ Preencha pelo menos um campo.")
            return
        
        # Validation
        if validate:
            validation_errors = validate_document(clean_doc, collection_name)
            if validation_errors:
                st.error("❌ Erros de validação encontrados:")
                for error in validation_errors:
                    st.error(f"• {error}")
                return
        
        # Prepare document for insertion
        prepared_doc = prepare_doc_for_save(clean_doc)
        
        # Insert document
        result = db[collection_name].insert_one(prepared_doc)
        st.success(f"✅ Documento inserido com sucesso! ID: {result.inserted_id}")
        
        # Show inserted document preview
        with st.expander("👁️ Documento Inserido", expanded=True):
            st.json(convert_objectid_to_str(prepared_doc))
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao inserir documento: {e}")

def validate_document(doc, collection_name):
    """Validate document before insertion"""
    errors = []
    
    # Check for required fields based on existing documents
    existing_docs = list(db[collection_name].find({}).limit(5))
    
    if existing_docs:
        # Find common required fields (present in most documents)
        field_frequency = {}
        for existing_doc in existing_docs:
            for field in existing_doc.keys():
                if field != '_id':
                    field_frequency[field] = field_frequency.get(field, 0) + 1
        
        required_fields = [field for field, freq in field_frequency.items() 
                          if freq >= len(existing_docs) * 0.8]  # Present in 80% of docs
        
        for req_field in required_fields:
            if req_field not in doc or not doc[req_field]:
                errors.append(f"Campo '{req_field}' é requerido (presente em {field_frequency[req_field]}/{len(existing_docs)} documentos)")
    
    # Validate reference fields
    for field, value in doc.items():
        if field.endswith('_id') and field != '_id' and value:
            try:
                # Check if referenced document exists
                ref_collection = field[:-3]  # Remove '_id'
                collections = db.list_collection_names()
                
                if ref_collection in collections:
                    ref_doc = db[ref_collection].find_one({"_id": bson.ObjectId(value)})
                    if not ref_doc:
                        errors.append(f"Referência inválida em '{field}': documento com ID '{value}' não encontrado em '{ref_collection}'")
                else:
                    # Just validate ObjectId format
                    if len(str(value)) != 24:
                        errors.append(f"Formato inválido para '{field}': deve ser um ObjectId válido")
            except Exception as e:
                errors.append(f"Erro ao validar '{field}': {e}")
    
    return errors

def create_hierarchy_field_manager(collection_name):
    """Manager for creating hierarchy fields"""
    st.markdown("#### 🏗️ Criar Campo Hierárquico")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_field_name = st.text_input(
            "Nome do campo hierárquico:", 
            value="parent_id",
            help="Ex: parent_id, categoria_pai_id, superior_id"
        )
    
    with col2:
        default_value = st.selectbox(
            "Valor padrão:",
            [None, "null", ""],
            format_func=lambda x: "null" if x is None else str(x)
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏗️ Criar Campo", type="primary"):
            if new_field_name:
                create_hierarchy_field(collection_name, new_field_name, default_value)
            else:
                st.error("Nome do campo é obrigatório")
    
    with col2:
        st.info("💡 **Dica:** Campos hierárquicos permitem organizar documentos em estruturas de árvore")

def create_hierarchy_field(collection_name, field_name, default_value):
    """Create a new hierarchy field"""
    try:
        update_value = None if default_value in [None, "null"] else default_value
        
        result = db[collection_name].update_many(
            {},
            {"$set": {field_name: update_value}}
        )
        
        st.success(f"✅ Campo '{field_name}' criado! {result.modified_count} documentos atualizados.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao criar campo: {e}")

def create_hierarchy_tools(collection_name, field_name):
    """Tools for managing hierarchy"""
    st.markdown(f"#### 🔧 Ferramentas para '{field_name}'")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Resetar Campo:**")
        if st.button(f"🔄 Resetar {field_name}", type="secondary"):
            try:
                result = db[collection_name].update_many(
                    {},
                    {"$set": {field_name: None}}
                )
                st.success(f"✅ Campo resetado! {result.modified_count} documentos atualizados.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro: {e}")
    
    with col2:
        st.markdown("**Remover Campo:**")
        if st.button(f"🗑️ Remover {field_name}", type="secondary"):
            try:
                result = db[collection_name].update_many(
                    {},
                    {"$unset": {field_name: ""}}
                )
                st.success(f"✅ Campo removido! {result.modified_count} documentos atualizados.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro: {e}")

def create_relations_manager(collection_name, relations, collections):
    """Advanced relations manager"""
    st.markdown("### 🔗 Gerenciador de Relações Avançado")
    
    # Current relations
    if relations[collection_name]:
        st.markdown(f"#### Relações Ativas em '{collection_name}':")
        
        for field, target_collection in relations[collection_name].items():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{field}** → `{target_collection}`")
                
                # Show statistics
                docs_with_relation = list(db[collection_name].find({field: {"$ne": None, "$ne": ""}}))
                st.caption(f"{len(docs_with_relation)} documentos com esta relação")
            
            with col2:
                if st.button(f"📊 Analisar", key=f"analyze_{field}"):
                    analyze_relation(collection_name, field, target_collection)
            
            with col3:
                if st.button(f"🔧 Gerenciar", key=f"manage_{field}"):
                    manage_relation(collection_name, field, target_collection)
    
    else:
        st.info(f"Nenhuma relação automática detectada em '{collection_name}'.")
    
    # Create new relation
    st.markdown("---")
    st.markdown("#### ➕ Criar Nova Relação")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        new_relation_field = st.text_input(
            "Nome do campo de relação:",
            placeholder="ex: categoria_id"
        )
    
    with col2:
        target_collection = st.selectbox(
            "Coleção de destino:",
            [None] + [c for c in collections if c != collection_name],
            format_func=lambda x: "Selecionar..." if x is None else x
        )
    
    with col3:
        if st.button("🔗 Criar Relação", type="primary"):
            if new_relation_field and target_collection:
                create_new_relation(collection_name, new_relation_field, target_collection)
            else:
                st.error("Preencha todos os campos")

def analyze_relation(collection_name, field, target_collection):
    """Analyze relation statistics"""
    with st.expander(f"📊 Análise: {field} → {target_collection}", expanded=True):
        # Get relation data
        docs_with_relation = list(db[collection_name].find({field: {"$ne": None, "$ne": ""}}))
        docs_without_relation = list(db[collection_name].find({field: {"$in": [None, ""]}}))
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Com Relação", len(docs_with_relation))
        
        with col2:
            st.metric("Sem Relação", len(docs_without_relation))
        
        with col3:
            total_docs = len(docs_with_relation) + len(docs_without_relation)
            coverage = (len(docs_with_relation) / total_docs * 100) if total_docs > 0 else 0
            st.metric("Cobertura", f"{coverage:.1f}%")
        
        with col4:
            # Check for broken references
            broken_refs = 0
            for doc in docs_with_relation:
                try:
                    ref_exists = db[target_collection].find_one({"_id": bson.ObjectId(doc[field])})
                    if not ref_exists:
                        broken_refs += 1
                except:
                    broken_refs += 1
            
            st.metric("Refs. Quebradas", broken_refs, delta_color="inverse")
        
        # Show broken references if any
        if broken_refs > 0:
            st.warning(f"⚠️ {broken_refs} referências quebradas encontradas!")
            
            if st.button(f"🔧 Reparar Referências de {field}"):
                repair_broken_references(collection_name, field, target_collection)

def repair_broken_references(collection_name, field, target_collection):
    """Repair broken references"""
    try:
        docs_with_relation = list(db[collection_name].find({field: {"$ne": None, "$ne": ""}}))
        repaired_count = 0
        
        for doc in docs_with_relation:
            try:
                ref_exists = db[target_collection].find_one({"_id": bson.ObjectId(doc[field])})
                if not ref_exists:
                    # Set broken reference to None
                    db[collection_name].update_one(
                        {"_id": doc["_id"]},
                        {"$set": {field: None}}
                    )
                    repaired_count += 1
            except:
                # Invalid ObjectId format
                db[collection_name].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {field: None}}
                )
                repaired_count += 1
        
        st.success(f"✅ {repaired_count} referências quebradas reparadas!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao reparar referências: {e}")

def manage_relation(collection_name, field, target_collection):
    """Manage specific relation"""
    with st.expander(f"🔧 Gerenciar: {field} → {target_collection}", expanded=True):
        
        tab1, tab2, tab3 = st.tabs(["📝 Editar", "📊 Estatísticas", "🗑️ Remover"])
        
        with tab1:
            st.markdown("**Edição em Lote:**")
            
            # Get available target documents
            target_docs = list(db[target_collection].find({}))
            target_docs = convert_objectid_to_str(target_docs)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Filter source documents
                filter_option = st.selectbox("Filtrar documentos:", ["Todos", "Com relação", "Sem relação"])
                
                if filter_option == "Com relação":
                    source_docs = list(db[collection_name].find({field: {"$ne": None, "$ne": ""}}))
                elif filter_option == "Sem relação":
                    source_docs = list(db[collection_name].find({field: {"$in": [None, ""]}}))
                else:
                    source_docs = list(db[collection_name].find({}))
                
                source_docs = convert_objectid_to_str(source_docs)
                st.info(f"{len(source_docs)} documentos encontrados")
            
            with col2:
                # Select new target
                new_target_id = st.selectbox(
                    "Nova relação:",
                    [None] + [doc["_id"] for doc in target_docs],
                    format_func=lambda x: "Remover relação" if x is None else next(
                        (doc.get("name", doc.get("title", f"ID: {x}")) 
                         for doc in target_docs if doc["_id"] == x), str(x)
                    )
                )
            
            if st.button("🔄 Aplicar Alteração em Lote"):
                apply_bulk_relation_change(collection_name, field, source_docs, new_target_id)
        
        with tab2:
            show_relation_statistics(collection_name, field, target_collection)
        
        with tab3:
            st.warning("⚠️ **Atenção:** Esta ação removerá o campo de todos os documentos!")
            
            if st.button(f"🗑️ Remover Campo '{field}'", type="secondary"):
                remove_relation_field(collection_name, field)

def apply_bulk_relation_change(collection_name, field, source_docs, new_target_id):
    """Apply bulk relation change"""
    try:
        doc_ids = [bson.ObjectId(doc["_id"]) for doc in source_docs]
        
        result = db[collection_name].update_many(
            {"_id": {"$in": doc_ids}},
            {"$set": {field: new_target_id}}
        )
        
        st.success(f"✅ {result.modified_count} documentos atualizados!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro na alteração em lote: {e}")

def show_relation_statistics(collection_name, field, target_collection):
    """Show detailed relation statistics"""
    st.markdown("**Estatísticas Detalhadas:**")
    
    # Get relation distribution
    pipeline = [
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    relation_stats = list(db[collection_name].aggregate(pipeline))
    
    if relation_stats:
        # Create chart data
        chart_data = []
        for stat in relation_stats[:10]:  # Top 10
            target_name = "Sem relação"
            if stat["_id"]:
                try:
                    target_doc = db[target_collection].find_one({"_id": bson.ObjectId(stat["_id"])})
                    if target_doc:
                        target_name = target_doc.get("name", target_doc.get("title", str(stat["_id"])))
                    else:
                        target_name = f"Ref. quebrada: {stat['_id']}"
                except:
                    target_name = f"ID inválido: {stat['_id']}"
            
            chart_data.append({
                "Target": target_name,
                "Count": stat["count"]
            })
        
        # Display chart
        df_chart = pd.DataFrame(chart_data)
        st.bar_chart(df_chart.set_index("Target"))
        
        # Display table
        st.dataframe(df_chart, use_container_width=True)

def remove_relation_field(collection_name, field):
    """Remove relation field completely"""
    try:
        result = db[collection_name].update_many(
            {},
            {"$unset": {field: ""}}
        )
        
        st.success(f"✅ Campo '{field}' removido de {result.modified_count} documentos!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao remover campo: {e}")

def create_new_relation(collection_name, field_name, target_collection):
    """Create a new relation field"""
    try:
        # Add field to all documents with null value
        result = db[collection_name].update_many(
            {},
            {"$set": {field_name: None}}
        )
        
        st.success(f"✅ Relação '{field_name}' → '{target_collection}' criada! {result.modified_count} documentos atualizados.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao criar relação: {e}")

def create_details_explorer(collection_name, docs, relations, collections):
    """Enhanced details explorer"""
    st.markdown("### 📊 Explorador de Detalhes Avançado")
    
    if not docs:
        st.info("Nenhum documento disponível para explorar.")
        return
    
    # Document selector with search
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_term = st.text_input("🔍 Buscar documento:", placeholder="Digite nome, ID ou qualquer campo...")
    
    with col2:
        sort_by = st.selectbox("Ordenar por:", ["_id", "name", "title"] + [k for k in docs[0].keys() if k not in ["_id", "name", "title"]])
    
    # Filter and sort documents
    filtered_docs = docs
    if search_term:
        filtered_docs = [doc for doc in docs 
                        if any(search_term.lower() in str(v).lower() for v in doc.values())]
    
    # Sort documents
    try:
        filtered_docs = sorted(filtered_docs, key=lambda x: str(x.get(sort_by, "")))
    except:
        pass  # Keep original order if sorting fails
    
    if not filtered_docs:
        st.warning("Nenhum documento encontrado com o termo de busca.")
        return
    
    # Document selection
    doc_options = [doc["_id"] for doc in filtered_docs]
    doc_labels = [
        f"{doc.get('name', doc.get('title', doc['_id']))} (ID: {doc['_id']})"
        for doc in filtered_docs
    ]
    
    selected_doc_id = st.selectbox(
        f"Documento ({len(filtered_docs)} encontrados):",
        doc_options,
        format_func=lambda x: doc_labels[doc_options.index(x)] if x in doc_options else str(x)
    )
    
    if selected_doc_id:
        selected_doc = next(doc for doc in filtered_docs if doc["_id"] == selected_doc_id)
        
        # Main document view
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### 📄 Dados do Documento")
            
            # Editable document view
            with st.expander("✏️ Edição Rápida", expanded=False):
                edit_document_inline(collection_name, selected_doc)
            
            # JSON view with copy button
            st.json(selected_doc)
            
            # Document metadata
            st.markdown("**Metadados:**")
            st.write(f"• **Campos:** {len(selected_doc)}")
            st.write(f"• **Tamanho (JSON):** {len(json.dumps(selected_doc))} caracteres")
        
        with col2:
            st.markdown("#### 🔗 Dados Relacionados")
            
            # Show related data from references
            show_related_data(selected_doc, collection_name, relations)
            
            # Show reverse relations
            st.markdown("#### 🔍 Referências Reversas")
            show_reverse_relations(selected_doc_id, collection_name, collections)
        
        # Navigation tools
        st.markdown("---")
        st.markdown("#### 🚀 Navegação Rápida")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Previous/Next navigation
            current_index = doc_options.index(selected_doc_id)
            
            prev_disabled = current_index == 0
            next_disabled = current_index == len(doc_options) - 1
            
            if st.button("⬅️ Anterior", disabled=prev_disabled):
                if not prev_disabled:
                    # Navigate to previous document
                    pass  # Implement navigation logic
        
        with col2:
            # Jump to related collection
            if collection_name in relations and relations[collection_name]:
                related_collections = list(set(relations[collection_name].values()))
                jump_to_collection = st.selectbox(
                    "Ir para coleção relacionada:",
                    [None] + related_collections,
                    format_func=lambda x: "Selecionar..." if x is None else x
                )
                
                if jump_to_collection and st.button("🚀 Ir"):
                    st.session_state["selected_collection"] = jump_to_collection
                    st.rerun()
        
        with col3:
            if st.button("➡️ Próximo", disabled=next_disabled):
                if not next_disabled:
                    # Navigate to next document
                    pass  # Implement navigation logic
        
        with col2:
            # Jump to related collection
            if collection_name in relations and relations[collection_name]:
                related_collections = list(set(relations[collection_name].values()))
                jump_to_collection = st.selectbox(
                    "Ir para coleção relacionada:",
                    [None] + related_collections,
                    format_func=lambda x: "Selecionar..." if x is None else x
                )
                
                if jump_to_collection and st.button("🚀 Ir"):
                    st.session_state["selected_collection"] = jump_to_collection
                    st.rerun()
        
        with col3:
            # Document actions
            with st.popover("🛠️ Ações", use_container_width=True):
                if st.button("📋 Copiar JSON", use_container_width=True):
                    st.code(json.dumps(selected_doc, indent=2, ensure_ascii=False))
                
                if st.button("📤 Exportar Documento", use_container_width=True):
                    export_single_document(selected_doc, collection_name)
                
                if st.button("🗑️ Deletar Documento", type="secondary", use_container_width=True):
                    delete_single_document(collection_name, selected_doc_id)

def edit_document_inline(collection_name, doc):
    """Enhanced inline document editing"""
    with st.form(f"edit_document_{doc['_id']}"):
        edited_data = {}
        
        # Organize fields in columns
        field_items = list(doc.items())
        mid_point = len(field_items) // 2
        
        col1, col2 = st.columns(2)
        
        with col1:
            for key, value in field_items[:mid_point]:
                if key == '_id':
                    st.text_input("ID (somente leitura)", value=value, disabled=True)
                    continue
                
                edited_data[key] = create_field_editor(key, value)
        
        with col2:
            for key, value in field_items[mid_point:]:
                if key == '_id':
                    continue
                
                edited_data[key] = create_field_editor(key, value, key_suffix="_col2")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.form_submit_button("💾 Salvar", type="primary"):
                save_document_changes(collection_name, doc['_id'], edited_data)
        
        with col2:
            if st.form_submit_button("🔄 Resetar"):
                st.rerun()
        
        with col3:
            if st.form_submit_button("📋 Preview JSON"):
                st.json(edited_data)

def create_field_editor(key, value, key_suffix=""):
    """Create appropriate editor for field type"""
    editor_key = f"edit_{key}{key_suffix}"
    
    if isinstance(value, bool):
        return st.checkbox(f"**{key}**", value=value, key=editor_key)
    elif isinstance(value, (int, float)):
        return st.number_input(f"**{key}**", value=value, key=editor_key)
    elif isinstance(value, list):
        # Handle list fields
        list_str = ", ".join(str(item) for item in value)
        new_list_str = st.text_area(f"**{key}** (lista)", value=list_str, key=editor_key)
        return [item.strip() for item in new_list_str.split(",") if item.strip()]
    elif isinstance(value, dict):
        # Handle nested objects
        json_str = json.dumps(value, indent=2, ensure_ascii=False)
        new_json_str = st.text_area(f"**{key}** (objeto)", value=json_str, key=editor_key)
        try:
            return json.loads(new_json_str)
        except:
            return value  # Return original if JSON is invalid
    else:
        # String fields with special handling
        if key.lower() in ['email', 'e-mail']:
            return st.text_input(f"**{key}**", value=str(value), key=editor_key, placeholder="exemplo@email.com")
        elif key.lower() in ['url', 'link', 'website']:
            return st.text_input(f"**{key}**", value=str(value), key=editor_key, placeholder="https://...")
        elif key.lower() in ['phone', 'telefone', 'celular']:
            return st.text_input(f"**{key}**", value=str(value), key=editor_key, placeholder="+55 11 99999-9999")
        elif len(str(value)) > 100:
            return st.text_area(f"**{key}**", value=str(value), key=editor_key)
        else:
            return st.text_input(f"**{key}**", value=str(value), key=editor_key)

def save_document_changes(collection_name, doc_id, edited_data):
    """Save changes to document"""
    try:
        # Clean and prepare data
        clean_data = {k: v for k, v in edited_data.items() 
                     if v not in [None, "", "None"] and pd.notna(v)}
        
        if not clean_data:
            st.warning("⚠️ Nenhum dado válido para salvar.")
            return
        
        # Prepare for saving
        prepared_data = prepare_doc_for_save(clean_data)
        
        result = db[collection_name].update_one(
            {"_id": bson.ObjectId(doc_id)},
            {"$set": prepared_data}
        )
        
        if result.modified_count > 0:
            st.success("✅ Documento atualizado com sucesso!")
            st.rerun()
        else:
            st.info("ℹ️ Nenhuma alteração detectada.")
    
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

def show_related_data(doc, collection_name, relations):
    """Show data from related collections"""
    if collection_name not in relations or not relations[collection_name]:
        st.info("Nenhuma relação encontrada.")
        return
    
    for field, target_collection in relations[collection_name].items():
        if field in doc and doc[field]:
            try:
                ref_id = bson.ObjectId(doc[field]) if isinstance(doc[field], str) else doc[field]
                ref_doc = db[target_collection].find_one({"_id": ref_id})
                
                if ref_doc:
                    ref_doc = convert_objectid_to_str(ref_doc)
                    
                    with st.expander(f"🔗 {field} → {target_collection}", expanded=False):
                        # Show main info
                        name = ref_doc.get("name", ref_doc.get("title", ref_doc["_id"]))
                        st.markdown(f"**{name}**")
                        
                        # Show key fields
                        key_fields = ["name", "title", "description", "status", "type"]
                        for key_field in key_fields:
                            if key_field in ref_doc and ref_doc[key_field]:
                                st.write(f"• **{key_field}:** {ref_doc[key_field]}")
                        
                        # Show full data in collapsible section
                        with st.expander("Ver todos os dados", expanded=False):
                            st.json(ref_doc)
                        
                        # Quick actions
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"🚀 Ir para {target_collection}", key=f"goto_{field}"):
                                st.session_state["selected_collection"] = target_collection
                                st.rerun()
                        
                        with col2:
                            if st.button(f"🔄 Atualizar Referência", key=f"update_ref_{field}"):
                                update_reference_popup(collection_name, doc["_id"], field, target_collection)
                
                else:
                    st.warning(f"⚠️ {field}: Referência quebrada (ID: {doc[field]})")
                    
                    if st.button(f"🔧 Reparar {field}", key=f"repair_{field}"):
                        repair_single_reference(collection_name, doc["_id"], field)
            
            except Exception as e:
                st.error(f"❌ Erro ao carregar {field}: {e}")

def show_reverse_relations(doc_id, collection_name, collections):
    """Show documents that reference this document"""
    reverse_relations = get_related_documents(doc_id, collection_name, collections)
    
    if not reverse_relations:
        st.info("Nenhum documento referencia este item.")
        return
    
    for related_collection, related_docs in reverse_relations.items():
        if related_docs:
            with st.expander(f"📋 {related_collection} ({len(related_docs)} referências)", expanded=False):
                for related_doc in related_docs:
                    name = related_doc.get("name", related_doc.get("title", related_doc["_id"]))
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write(f"• **{name}** (ID: {related_doc['_id']})")
                    
                    with col2:
                        if st.button("👁️", key=f"view_{related_doc['_id']}", help="Ver detalhes"):
                            # Navigate to this document
                            st.session_state["selected_collection"] = related_collection
                            st.rerun()

def update_reference_popup(collection_name, doc_id, field, target_collection):
    """Popup for updating reference"""
    with st.popover(f"🔄 Atualizar {field}", use_container_width=True):
        # Get available options
        target_docs = list(db[target_collection].find({}))
        target_docs = convert_objectid_to_str(target_docs)
        
        options = [None] + [doc["_id"] for doc in target_docs]
        labels = ["(Remover referência)"] + [
            doc.get("name", doc.get("title", f"ID: {doc['_id']}"))
            for doc in target_docs
        ]
        
        new_ref = st.selectbox(
            "Nova referência:",
            options,
            format_func=lambda x: labels[options.index(x)] if x in options else str(x)
        )
        
        if st.button("💾 Atualizar Referência", type="primary"):
            try:
                result = db[collection_name].update_one(
                    {"_id": bson.ObjectId(doc_id)},
                    {"$set": {field: new_ref}}
                )
                
                if result.modified_count > 0:
                    st.success("✅ Referência atualizada!")
                    st.rerun()
                else:
                    st.warning("Nenhuma alteração feita.")
            
            except Exception as e:
                st.error(f"❌ Erro: {e}")

def repair_single_reference(collection_name, doc_id, field):
    """Repair a single broken reference"""
    try:
        result = db[collection_name].update_one(
            {"_id": bson.ObjectId(doc_id)},
            {"$set": {field: None}}
        )
        
        if result.modified_count > 0:
            st.success("✅ Referência quebrada removida!")
            st.rerun()
        else:
            st.warning("Nenhuma alteração feita.")
    
    except Exception as e:
        st.error(f"❌ Erro ao reparar: {e}")

def export_single_document(doc, collection_name):
    """Export single document"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{collection_name}_{doc['_id']}_{timestamp}.json"
    
    json_data = json.dumps(doc, indent=2, ensure_ascii=False)
    
    st.download_button(
        label="📥 Baixar JSON",
        data=json_data,
        file_name=filename,
        mime="application/json"
    )

def delete_single_document(collection_name, doc_id):
    """Delete single document with confirmation"""
    with st.popover("⚠️ Confirmar Exclusão", use_container_width=True):
        st.warning(f"Tem certeza que deseja deletar o documento `{doc_id}`?")
        st.caption("Esta ação não pode ser desfeita.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Sim, Deletar", type="secondary", use_container_width=True):
                try:
                    result = db[collection_name].delete_one({"_id": bson.ObjectId(doc_id)})
                    
                    if result.deleted_count > 0:
                        st.success("✅ Documento deletado!")
                        st.rerun()
                    else:
                        st.error("❌ Documento não encontrado.")
                
                except Exception as e:
                    st.error(f"❌ Erro ao deletar: {e}")
        
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.rerun()

# Additional utility functions for enhanced functionality

def create_data_visualization_tab(collection_name, docs):
    """Create data visualization tab"""
    if not docs:
        st.info("Nenhum dado disponível para visualização.")
        return
    
    st.markdown("### 📈 Visualizações de Dados")
    
    # Convert to DataFrame for analysis
    df = safe_dataframe_conversion(docs)
    
    if df.empty:
        st.warning("Não foi possível criar visualizações com os dados disponíveis.")
        return
    
    # Chart type selector
    chart_type = st.selectbox(
        "Tipo de visualização:",
        ["Distribuição de Campos", "Gráfico de Barras", "Série Temporal", "Estatísticas"]
    )
    
    if chart_type == "Distribuição de Campos":
        create_field_distribution_chart(df)
    elif chart_type == "Gráfico de Barras":
        create_bar_chart(df)
    elif chart_type == "Série Temporal":
        create_time_series_chart(df)
    elif chart_type == "Estatísticas":
        create_statistics_view(df)

def create_field_distribution_chart(df):
    """Create field distribution visualization"""
    # Field completeness
    completeness_data = []
    for col in df.columns:
        non_null_count = df[col].notna().sum()
        completeness_data.append({
            "Campo": col,
            "Preenchido": non_null_count,
            "Vazio": len(df) - non_null_count,
            "Percentual": (non_null_count / len(df)) * 100
        })
    
    completeness_df = pd.DataFrame(completeness_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Completude dos Campos")
        fig = px.bar(
            completeness_df,
            x="Campo",
            y="Percentual",
            title="Percentual de Campos Preenchidos",
            color="Percentual",
            color_continuous_scale="RdYlGn"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 📋 Tabela de Completude")
        st.dataframe(
            completeness_df[["Campo", "Preenchido", "Vazio", "Percentual"]],
            use_container_width=True
        )

def create_bar_chart(df):
    """Create customizable bar chart"""
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_columns = df.select_dtypes(include=['object', 'string']).columns.tolist()
    
    if not categorical_columns:
        st.warning("Nenhum campo categórico encontrado para criar gráfico de barras.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        x_axis = st.selectbox("Campo para eixo X:", categorical_columns)
    
    with col2:
        if numeric_columns:
            y_axis = st.selectbox("Campo para eixo Y (opcional):", [None] + numeric_columns)
        else:
            y_axis = None
    
    if x_axis:
        if y_axis:
            # Aggregate numeric data
            chart_data = df.groupby(x_axis)[y_axis].sum().reset_index()
            fig = px.bar(chart_data, x=x_axis, y=y_axis, title=f"{y_axis} por {x_axis}")
        else:
            # Count occurrences
            chart_data = df[x_axis].value_counts().reset_index()
            chart_data.columns = [x_axis, 'Count']
            fig = px.bar(chart_data, x=x_axis, y='Count', title=f"Distribuição de {x_axis}")
        
        st.plotly_chart(fig, use_container_width=True)

def create_time_series_chart(df):
    """Create time series visualization"""
    date_columns = []
    
    # Try to identify date columns
    for col in df.columns:
        if df[col].dtype == 'object':
            # Try to parse as date
            try:
                pd.to_datetime(df[col].head(), errors='raise')
                date_columns.append(col)
            except:
                pass
    
    if not date_columns:
        st.info("Nenhum campo de data encontrado. Tentando detectar campos que podem ser datas...")
        
        # Look for fields with date-like names
        potential_date_fields = [col for col in df.columns 
                               if any(word in col.lower() for word in ['date', 'time', 'created', 'updated', 'data'])]
        
        if potential_date_fields:
            st.write("Campos que podem conter datas:", potential_date_fields)
            selected_date_field = st.selectbox("Selecionar campo de data:", potential_date_fields)
            
            if selected_date_field:
                try:
                    df[selected_date_field] = pd.to_datetime(df[selected_date_field])
                    
                    # Create time series chart
                    daily_counts = df.groupby(df[selected_date_field].dt.date).size().reset_index()
                    daily_counts.columns = ['Data', 'Contagem']
                    
                    fig = px.line(daily_counts, x='Data', y='Contagem', 
                                title=f"Série Temporal - {selected_date_field}")
                    st.plotly_chart(fig, use_container_width=True)
                
                except Exception as e:
                    st.error(f"Erro ao processar campo de data: {e}")
        else:
            st.info("Nenhum campo de data detectado.")
    else:
        selected_date_field = st.selectbox("Campo de data:", date_columns)
        
        if selected_date_field:
            df[selected_date_field] = pd.to_datetime(df[selected_date_field])
            
            # Create time series chart
            daily_counts = df.groupby(df[selected_date_field].dt.date).size().reset_index()
            daily_counts.columns = ['Data', 'Contagem']
            
            fig = px.line(daily_counts, x='Data', y='Contagem', 
                        title=f"Série Temporal - {selected_date_field}")
            st.plotly_chart(fig, use_container_width=True)

def create_statistics_view(df):
    """Create comprehensive statistics view"""
    st.markdown("#### 📊 Estatísticas Gerais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Registros", len(df))
    
    with col2:
        st.metric("Total de Campos", len(df.columns))
    
    with col3:
        # Calculate data density
        total_cells = len(df) * len(df.columns)
        filled_cells = df.notna().sum().sum()
        density = (filled_cells / total_cells) * 100
        st.metric("Densidade dos Dados", f"{density:.1f}%")
    
    with col4:
        # Memory usage
        memory_usage = df.memory_usage(deep=True).sum()
        st.metric("Uso de Memória", f"{memory_usage / 1024:.1f} KB")
    
    # Detailed statistics for numeric columns
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if numeric_columns:
        st.markdown("#### 📈 Estatísticas Numéricas")
        
        selected_numeric = st.multiselect("Selecionar campos numéricos:", numeric_columns, default=numeric_columns[:3])
        
        if selected_numeric:
            stats_df = df[selected_numeric].describe()
            st.dataframe(stats_df, use_container_width=True)
            
            # Distribution plots
            for col in selected_numeric:
                fig = px.histogram(df, x=col, title=f"Distribuição de {col}")
                st.plotly_chart(fig, use_container_width=True)
    
    # Categorical data analysis
    categorical_columns = df.select_dtypes(include=['object', 'string']).columns.tolist()
    
    if categorical_columns:
        st.markdown("#### 📋 Análise Categórica")
        
        selected_categorical = st.selectbox("Campo categórico:", categorical_columns)
        
        if selected_categorical:
            value_counts = df[selected_categorical].value_counts()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Top 10 valores em {selected_categorical}:**")
                st.dataframe(value_counts.head(10), use_container_width=True)
            
            with col2:
                fig = px.pie(
                    values=value_counts.head(10).values,
                    names=value_counts.head(10).index,
                    title=f"Distribuição de {selected_categorical}"
                )
                st.plotly_chart(fig, use_container_width=True)

# Main app function enhancement
def app(lang, filters):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 15px; margin-bottom: 2rem;'>
            <h1 style='color: white; margin: 0; text-align: center;'>
                🗄️ MongoDB CRUD Manager Pro
            </h1>
            <p style='color: rgba(255,255,255,0.9); text-align: center; margin: 0.5rem 0 0 0;'>
                Gerenciamento CRUD Avançado com Drag-and-Drop e Visualizações
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Get collections and relations
    collections, relations = get_collections_with_relations()
    
    if not collections:
        st.error("Nenhuma coleção encontrada no banco de dados.")
        return

    # Collection selector with session state
    if "selected_collection" in st.session_state and st.session_state["selected_collection"] in collections:
        default_index = collections.index(st.session_state["selected_collection"])
    else:
        default_index = 0
    
    collection_name = st.selectbox(
        "📁 Selecionar Coleção", 
        collections,
        index=default_index,
        help="Escolha a coleção MongoDB para gerenciar"
    )

    if not collection_name:
        return

    collection = db[collection_name]
    docs = list(collection.find({}))
    docs = convert_objectid_to_str(docs)

    # Show collection info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Documentos", len(docs))
    with col2:
        if collection_name in relations and relations[collection_name]:
            st.metric("Relações", len(relations[collection_name]))
        else:
            st.metric("Relações", 0)
    with col3:
        hierarchy_fields = get_hierarchy_fields(docs)
        st.metric("Campos Hierárquicos", len(hierarchy_fields))
    with col4:
        # Calculate average document size
        if docs:
            avg_size = sum(len(json.dumps(doc)) for doc in docs) / len(docs)
            st.metric("Tamanho Médio", f"{avg_size:.0f} chars")
        else:
            st.metric("Tamanho Médio", "0 chars")

    # Enhanced tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 CRUD Pro", "🌳 Hierarquia", "🔗 Relações", "📊 Detalhes", "📈 Visualizações"])

    with tab1:
        advanced_crud_interface(collection_name, docs, relations)
        
        # Enhanced Add new document form
        st.markdown("---")
        st.markdown("### ➕ Formulário Inteligente de Inserção")
        
        with st.expander("Adicionar Novo Documento", expanded=not bool(docs)):
            # Get sample document structure if available
            sample_fields = {}
            if docs:
                for doc in docs[:5]:  # Use first 5 docs to determine structure
                    for field, value in doc.items():
                        if field not in sample_fields:
                            sample_fields[field] = type(value).__name__
            
            # Smart form generation
            create_smart_insertion_form(collection_name, sample_fields, relations)

    with tab2:
        st.markdown("### 🌳 Gestão Hierárquica Avançada")
        
        # Get potential hierarchy fields
        hierarchy_fields = get_hierarchy_fields(docs)
        
        if not hierarchy_fields:
            st.info("Nenhum campo hierárquico detectado.")
            create_hierarchy_field_manager(collection_name)
        else:
            # Select hierarchy field
            selected_hierarchy_field = st.selectbox(
                "🔧 Escolher campo hierárquico:",
                hierarchy_fields,
                help="Selecione qual campo usar para construir a hierarquia"
            )
            
            # Check if this field has hierarchical structure
            has_hierarchy = any(doc.get(selected_hierarchy_field) for doc in docs)
            
            if has_hierarchy:
                create_hierarchy_view(collection_name, selected_hierarchy_field)
            else:
                st.info(f"O campo '{selected_hierarchy_field}' existe mas não possui valores hierárquicos.")
                create_hierarchy_tools(collection_name, selected_hierarchy_field)

    with tab3:
        create_relations_manager(collection_name, relations, collections)

    with tab4:
        create_details_explorer(collection_name, docs, relations, collections)
    
    with tab5:
        create_data_visualization_tab(collection_name, docs)

