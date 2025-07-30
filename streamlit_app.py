def display_results(trailer: Trailer, placed: List[Box], left: List[Box], sku_groups: List[List[Box]], missing: pd.DataFrame):
    # Seção de Métricas no topo
    st.subheader("Indicadores de Performance")
    
    cols = st.columns(3)
    with cols[0]:
        vol_used = sum(b.volume for b in placed)
        utilizacao = vol_used / trailer.volume * 100 if trailer.volume > 0 else 0
        st.metric("**Taxa de Ocupação**", f"{utilizacao:.1f}%")
    
    with cols[1]:
        st.metric("Caixas Posicionadas", len(placed))
    
    with cols[2]:
        st.metric("Caixas Não Alocadas", len(left))

    # Seção de Visualização 3D abaixo
    st.subheader("Visualização Tridimensional da Carga")
    
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(111, projection='3d')
    
    # Configurações do gráfico (mantidas do código original)
    ax.set_xlim(0, trailer.c)
    ax.set_ylim(0, trailer.l)
    ax.set_zlim(0, trailer.a)
    ax.view_init(elev=25, azim=-60)
    
    # Contorno do trailer
    ax.add_collection3d(
        Line3DCollection(
            create_cube_edges(0, 0, 0, trailer.c, trailer.l, trailer.a),
            colors="#404040",
            linewidths=0.8
        )
    )
    
    # Plotagem das caixas
    if placed:
        unique_skus = {b.id.rsplit("-", 1)[0] for b in placed}
        cmap = plt.get_cmap("tab20")
        colors = {sku: cmap(i % 20) for i, sku in enumerate(unique_skus)}
        
        for b in placed:
            sku_base = b.id.rsplit("-", 1)[0]
            add_box_to_plot(ax, b, colors[sku_base])

    st.pyplot(fig)
    
    # Seção de informações adicionais
    if sku_groups and (remaining_vol := trailer.volume - vol_used) > 0:
        if last_group := [g for g in sku_groups if g][-1]:
            sample = last_group[0]
            adicional = int(remaining_vol // sample.volume)
            if adicional > 0:
                st.divider()
                st.markdown(f"""
                **📦 Espaço Residual**
                - **{adicional} unidades** adicionais
                - **SKU:** {sample.id.rsplit("-", 1)[0]}  
                - **Dimensões:** {sample.c}m × {sample.l}m × {sample.a}m
                """)
    
    with st.expander("⚠️ SKUs Não Mapeados"):
        if not missing.empty:
            st.dataframe(
                missing[["COD SKU", "QTDE"]],
                column_config={"COD SKU": "SKU", "QTDE": "Quantidade"},
                use_container_width=True
            )
