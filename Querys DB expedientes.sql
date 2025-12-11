CREATE DATABASE sis_exp;
USE sis_exp;


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
  
  
CREATE TABLE expediente (
  id INT AUTO_INCREMENT PRIMARY KEY ,
  aseguradora_id INT NOT NULL,
  usuario_id INT NOT NULL,
  juzgado_id INT NOT NULL,
  estado ENUM('Pendiente', 'En Curso', 'Cerrado'),
  fecha DATE,
  FOREIGN KEY (aseguradora_id) REFERENCES aseguradora(id),
  FOREIGN KEY (usuario_id) REFERENCES usuario(id),
  FOREIGN KEY (juzgado_id) REFERENCES juzgado(id)
  );
  
  
insert into usuario values 
(null, 'Kurt', 'Kelly','kurt12','1234'),
(null, 'Jose', 'Alvarino','jose28','1234'), 
(null, 'Maryon', 'Torres','maryon23','1234'),
(null, 'Eimy', 'Mendez', 'eimy25','1234'),
(null, 'Aaron', 'Newball','aaron26','1234'),
(null, 'Eric', 'Murillo', 'eric27','1234'),
(null, 'Karen', 'Arauz', 'karen15','1234');


insert into juzgado values (null, 'Juzgado 5TO Pedregal'),
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


insert into expediente values (null,1,1,1,'Pendiente','2019-01-07'), 
(null,2,2,2,'En Curso','2019-01-07'), 
(null,1,3,1,'Pendiente','2019-01-07'), 
(null,3,4,4,'Cerrado','2019-01-07'), 
(null,4,5,3,'Pendiente','2019-01-07'), 
(null,5,6,6,'En Curso','2019-01-07'), 
(null,2,7,5,'Cerrado','2019-01-07');


