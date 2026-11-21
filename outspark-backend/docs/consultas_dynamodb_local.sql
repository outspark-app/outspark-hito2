-- Selecciona una consulta y ejecuta con Command + Enter en Outspark local.
-- PK agrupa registros relacionados. SK distingue y ordena dentro del grupo.
-- La pareja PK + SK identifica un ítem dentro de cada tabla.
-- Los textos USER#, POST#, PROFILE, etc. son convenciones de Outspark.
-- Cada consulta filtra una PK concreta; selecciona solo una antes de ejecutar.
-- Los usuarios fb-* son cuentas locales de simulación, no identidades reales.

-- 1. Perfil local de simulación del usuario 1.
SELECT * FROM "Outspark-local-profiles"
WHERE PK = 'USER#fb-1' AND SK = 'PROFILE';

-- 2. Dataset completo: manifiesto y recuentos.
SELECT PK, SK, dataset_id, status, counts FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009' AND SK = 'MANIFEST';

-- 3. Nodo 1: grado y contadores históricos.
SELECT * FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009' AND SK = 'NODE#000000000001';

-- 4. Primer bloque de vecinos del nodo 1.
SELECT * FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009#USER#1' AND SK = 'ADJ#00000000';

-- 5. Primer bloque de filas originales de amistad del nodo 1.
SELECT * FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009#USER#1' AND SK = 'LINK#00000000';

-- 6. Preferencias de Ana: la demo ya tiene el ítem PREFS guardado.
-- Las cuentas fb-* usan preferencias predeterminadas hasta guardar cambios.
SELECT * FROM "Outspark-local-profiles"
WHERE PK = 'USER#ana' AND SK = 'PREFS';

-- 7. Perfil y preferencias juntos: se consulta el grupo USER#ana.
SELECT * FROM "Outspark-local-profiles"
WHERE PK = 'USER#ana';

-- 8. Contactos creados en la demo para Diego (Bruno y Carla).
-- Las amistades históricas fb-* se consultan en Network Analysis (consulta 4).
SELECT * FROM "Outspark-local-connections"
WHERE PK = 'USER#diego';

-- 9. Amistad canónica entre Bruno y Diego.
-- Los IDs de la pareja se ordenan para guardar una sola amistad canónica.
SELECT * FROM "Outspark-local-connections"
WHERE PK = 'FRIEND#bruno#diego' AND SK = 'META';

-- 10. Catálogo pequeño de comunidades.
SELECT * FROM "Outspark-local-communities"
WHERE PK = 'CATALOG#COMM';

-- 11. Catálogo pequeño de temas.
SELECT * FROM "Outspark-local-communities"
WHERE PK = 'CATALOG#TOPIC';

-- 12. Datos de la comunidad Diseño.
SELECT * FROM "Outspark-local-communities"
WHERE PK = 'COMM#diseno' AND SK = 'META';

-- 13. Pertenencia de fb-1 a Diseño.
SELECT * FROM "Outspark-local-communities"
WHERE PK = 'USER#fb-1' AND SK = 'MEMBER#diseno';

-- 14. Miembros de Diseño: rango de SK que empieza por MEMBER#.
SELECT * FROM "Outspark-local-communities"
WHERE PK = 'COMM#diseno' AND SK BETWEEN 'MEMBER#' AND 'MEMBER$';

-- 15. Publicación nueva del recorrido HTTP verificado después de migrar.
-- Para otra publicación, reemplaza el UUID después de POST# en 15-18.
SELECT * FROM "Outspark-local-publishing"
WHERE PK = 'POST#e6032c10-50b3-4824-901c-57e540256e66' AND SK = 'META';

-- 16. Todos los registros de esta publicación: original, eventos y participación.
SELECT * FROM "Outspark-local-publishing"
WHERE PK = 'POST#e6032c10-50b3-4824-901c-57e540256e66';

-- 17. Publicar y republicar: parent_event_id enlaza cada evento con su padre.
-- El evento raíz tiene parent_event_id = null. Esto permite reconstruir la ruta.
SELECT PK, SK, actor_id, event_id, parent_event_id, created_at
FROM "Outspark-local-publishing"
WHERE PK = 'POST#e6032c10-50b3-4824-901c-57e540256e66'
AND SK BETWEEN 'EVENT#' AND 'EVENT$';

-- 18. Participación de fb-2: registra el evento que republicó este usuario.
SELECT * FROM "Outspark-local-publishing"
WHERE PK = 'POST#e6032c10-50b3-4824-901c-57e540256e66' AND SK = 'ACTOR#fb-2';

-- 19. Feed que recibió fb-3 en el mismo recorrido.
-- Abre el JSON cards: sources contiene los eventos utilizados para cada tarjeta.
-- Las rutas completas se consultan mediante el endpoint de provenance de Swagger.
SELECT * FROM "Outspark-local-discovery"
WHERE PK = 'FEED#afec5960-c52f-4636-8ae2-35bbb6a8b78c' AND SK = 'META';

-- 20. Historial de snapshots del destinatario fb-3.
-- Cada snapshot_id apunta a FEED#snapshot_id / META, como en la consulta 19.
SELECT * FROM "Outspark-local-discovery"
WHERE PK = 'USER#fb-3';

-- 21. Primer bloque de eventos históricos recibidos en el muro del nodo 1.
-- Son filas del dataset sin texto de contenido; no son republicaciones de Outspark.
SELECT * FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009#USER#1' AND SK = 'WALL_IN#00000000';

-- 22. Primer bloque de eventos históricos escritos por el nodo 1.
SELECT * FROM "Outspark-local-network-analysis"
WHERE PK = 'DATASET#facebook-wosn2009#USER#1' AND SK = 'WALL_OUT#00000000';
