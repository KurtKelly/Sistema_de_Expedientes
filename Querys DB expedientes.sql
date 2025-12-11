
#Creacion de la base de datos

CREATE DATABASE sis_exp;
USE sis_exp;

#Creación de tablas

CREATE TABLE usuario (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(45) NOT NULL,
  apellido VARCHAR(45) NOT NULL,
  username VARCHAR(45) NOT NULL,
  pass VARCHAR(45) NOT NULL
);

  CREATE TABLE juzgado (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre_juzgado VARCHAR(45) NOT NULL);


CREATE TABLE aseguradora (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre_aseguradora VARCHAR(45) NOT NULL);


  CREATE TABLE caso (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre_caso VARCHAR(45) NOT NULL);

CREATE TABLE expediente (
  id INT AUTO_INCREMENT PRIMARY KEY ,
  aseguradora_id INT NOT NULL,
  usuario_id INT NOT NULL,
  juzgado_id INT NOT NULL,
  caso_id INT NOT NULL,
  estado ENUM('Pendiente', 'En Curso', 'Cerrado'),
  fecha DATE,
  FOREIGN KEY (aseguradora_id) REFERENCES aseguradora(id),
  FOREIGN KEY (usuario_id) REFERENCES usuario(id),
  FOREIGN KEY (juzgado_id) REFERENCES juzgado(id),
  FOREIGN KEY (caso_id) REFERENCES caso(id)
  );


 #Poblacion de tablas

insert into usuario values
(null, 'Kurt', 'Kelly','kurt12','1234'),
(null, 'Jose', 'Alvarino','jose28','1234'),
(null, 'Maryon', 'Torres','maryon23','1234'),
(null, 'Eimy', 'Mendez', 'eimy25','1234'),
(null, 'Aaron', 'Newball','aaron26','1234'),
(null, 'Eric', 'Murillo', 'eric27','1234'),
(null, 'Karen', 'Arauz', 'karen15','1234');


insert into juzgado values
(null, 'Juzgado 5TO Pedregal'),
(null, 'Juzgado 4TO Pedregal'),
(null, 'Juzgado 3RO Pedregal'),
(null, 'Juzgado 1RO Pedregal'),
(null, 'Chitre'),
(null, 'Alcaldia Panama');



insert into aseguradora values (null, 'ASSA'),
(null, 'ANCON'),
(null, 'CONANCE'),
(null, 'PARTICULAR'),
(null, 'INTEROCEANICA');

insert into caso values
(null,"TRANSITO"),
(null,"PENAL");


insert into expediente values
(null,1,1,1,1,'Pendiente','2019-01-07'),
(null,2,2,2,1,'En Curso','2019-01-07'),
(null,1,3,1,2,'Pendiente','2019-01-07'),
(null,3,4,4,2,'Cerrado','2019-01-07'),
(null,4,5,3,1,'Pendiente','2019-01-07'),
(null,5,6,6,1,'En Curso','2019-01-07'),
(null,2,7,5,2,'Cerrado','2019-01-07');





# VISTAS

# Vista de detalle completo del expediente con nombres de catálogos
CREATE OR REPLACE VIEW vista_expedientes_detalle AS
SELECT
  e.id,
  e.estado,
  e.fecha,
  e.aseguradora_id,
  a.nombre_aseguradora AS aseguradora,
  e.usuario_id,
  CONCAT(u.nombre, ' ', u.apellido) AS usuario,
  u.username AS usuario_username,
  e.juzgado_id,
  j.nombre_juzgado AS juzgado,
  e.caso_id,
  c.nombre_caso AS caso
FROM expediente e
JOIN aseguradora a ON a.id = e.aseguradora_id
JOIN usuario u ON u.id = e.usuario_id
JOIN juzgado j ON j.id = e.juzgado_id
JOIN caso c ON c.id = e.caso_id;

# Vista de solo expedientes pendientes
CREATE OR REPLACE VIEW vista_expedientes_pendientes AS
SELECT *
FROM vista_expedientes_detalle
WHERE estado = 'Pendiente';

# Vista de productividad por usuario (cantidad por estado)
CREATE OR REPLACE VIEW vista_productividad_usuario AS
SELECT
  u.id AS usuario_id,
  CONCAT(u.nombre, ' ', u.apellido) AS usuario,
  e.estado,
  COUNT(*) AS total
FROM usuario u
JOIN expediente e ON e.usuario_id = u.id
GROUP BY u.id, usuario, e.estado
ORDER BY usuario, e.estado;


# Backup de la base de datos:
-- mysqldump -h 127.0.0.1 -u root -p sis_exp > backup_sis_exp.sql

# Restaurar:
-- mysql -h 127.0.0.1 -u root -p sis_exp < backup_sis_exp.sql




